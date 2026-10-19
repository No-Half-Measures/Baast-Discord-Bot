import datetime
import logging
import json
import sys
from typing import Optional
from asgiref.sync import sync_to_async
import arrow
from pytz import timezone as TZ

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound

from django.db.models import (Model, SlugField, ImageField, AutoField, BigIntegerField, CharField, JSONField, TextField, DateTimeField, SmallIntegerField, BooleanField, 
                              ForeignKey, CASCADE, SET_NULL, UniqueConstraint)
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin
from django.utils.text import slugify

from hikari import Guild, TextableChannel
import stripe

from cache.models import DiscordUser
from bot.bot.utils.enums import SignupOption

from loguru import logger

from django.conf import settings

GOOGLE_SERVICE_ACCOUNT_FILE = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE')
# Calendar ID (usually your email address)
CALENDAR_ID = 'baast-events@baast-337223.iam.gserviceaccount.com'#'your_calendar_id@group.calendar.google.com'
SCOPES = ['https://www.googleapis.com/auth/calendar']


def convert(time: str) -> tuple[int, int, int]:
    """Convert time string to hours, minutes, seconds tuple.
    
    Supports formats:
    - "6:0:0" -> (6, 0, 0)
    - "2d,12:30:0" -> (60, 30, 0)  # 2 days + 12 hours = 60 hours
    """
    parts = time.split(':')
    
    # Parse hours (first part)
    hours_str = parts[0].lower()
    if 'd' in hours_str:
        # Handle days format: "2d,12" -> 2*24 + 12 = 60 hours
        day_parts = hours_str.split("days,", 1)
        hours = 24 * int(day_parts[0])
        if len(day_parts) > 1:
            hours += int(day_parts[1])
    else:
        hours = int(hours_str)
    
    # Parse minutes and seconds
    minutes = int(parts[1]) if len(parts) > 1 else 0
    seconds = int(parts[2]) if len(parts) > 2 else 0
    
    return hours, minutes, seconds

class Config(ExportModelOperationsMixin('config'), Model):
    id = AutoField(primary_key=True)
    guild = BigIntegerField()
    
    stripeSubscriptionId = CharField(max_length=100, null=True)

    event_channels : list[int] = JSONField(default=list)

    log_channel = BigIntegerField(default=0)
    
    reminders : list[dict] = JSONField(default=[{
        "name": 'Signup Reminder',
        "sequence": 'before',
        "time": 72,
        "color": 'ff0000',
        "target": 'nosign',
        "message": 'You are yet to set an attendance status for event **{title}**\n'
        'Please set your attendance status for **[{title}]({discord_url})** on {datetime_long} : {datetime_relative}'
    }, {
        "name": 'Tentative Reminder',
        "sequence": 'before',
        "time": 48,
        "color": '0000ff',
        "target": 'tentative',
        "message": 'You are currently set as Tentative for event **{title}**\n'
        'Please update your status for **[{title}]({discord_url})** {datetime_long} : {datetime_relative}'
    }, {
        "name": 'Event Reminder',
        "sequence": 'before',
        "time": 3,
        "color": '00ff00',
        "target": 'attending',
        "message": 'The event **{title}** is starting {datetime_relative}!'
    },
    ])
    backup_reminders : list[dict] = JSONField(default=list) # For backup purposes for when a guild is no longer premium
    
    autoclean_t = TextField(default='2:0:0')
    checkin_t = TextField(default='6:0:0')

    calendar_enabled = BigIntegerField(default=0)
    calendar_id = TextField(default=None, null=True)
    
    # 0 = Delete, 1 = Archive
    thread_delete_method = SmallIntegerField(default=0)
    # 0 = Truncate, 1 = Overflow
    signup_overflow_method = SmallIntegerField(default=0)
    
    # Premium
    p_expire_date = DateTimeField(auto_now_add=True, null=True)
    p_sheetid = TextField(default=None, null=True)
    p_archive_sheetid = TextField(default=None, null=True)
    
    # Delete
    delete_date = DateTimeField(default=None, db_column='mark_to_delete', null=True)
    
    def __str__(self):
        return str(f'{self.id}::{self.guild}')
    
    @property
    def id(self):
        return self.id
    
    async def log(self, guild: Guild) -> TextableChannel:
        logChnl = guild.get_channel(self.log_channel)
        return logChnl
    
    @property
    def logs_enabled(self) -> bool:
        return self.log_channel != 0
    
    @property
    def is_premium(self) -> bool:
        now = timezone.now()
        return now <= self.p_expire_date
    
    @property
    def is_sub_cancelled(self) -> bool:
        if self.stripeSubscriptionId is None:
            return False
        
        try:
            subscription = stripe.Subscription.retrieve(self.stripeSubscriptionId)
            return subscription.status == 'canceled' or subscription.canceled_at
        except:
            return False
    
    @property
    def checkin_time(self) -> tuple[int,int,int]:
        return convert(self.checkin_t)

    @property
    def autoclean(self) -> tuple[int,int,int]:
        return convert(self.autoclean_t)
    
    def tentativeDate(self, eventDate: arrow.Arrow) -> arrow.Arrow:
        tentativeDate = None
        for r in self.reminders:
            if 'target' in r.keys() and r['target'] == 'tentative':
                if tentativeDate == None or tentativeDate < eventDate.shift(hours=-r['time']):
                    tentativeDate = eventDate.shift(hours=-r['time'])
        return tentativeDate if tentativeDate else eventDate.shift(hours=48)
    
    def signupDate(self, eventDate: arrow.Arrow) -> arrow.Arrow:
        signupDate = None
        for r in self.reminders:
            if 'target' in r.keys() and r['target'] == 'nosign':
                if signupDate == None or signupDate < eventDate.shift(hours=-int(r['time'])):
                    signupDate = eventDate.shift(hours=-int(r['time']))
        return signupDate if signupDate else eventDate.shift(hours=-72)

class Option_Presets(Model):
    id = AutoField(primary_key=True)
    gid = ForeignKey(to=Config, on_delete=CASCADE, null=False, db_column='guild_id')
    name = TextField(null=False)
    options: list = JSONField(default=dict, null=False)
    len = SmallIntegerField(null=False)
    use_capacity = BooleanField(default=False)
    split_capacity = BooleanField(default=False)
    
    def __str__(self):
        return str(f'Option Preset {self.id}::{self.name}')
    
    def Config(self) -> Config:
        return self.gid
    
    @property
    def to_string(self) -> str:
        string = ""
        for option in self.options:
            string += f"{option['label']}, "
        return string
    
    @property
    def to_html(self) -> str:
        string = ""
        for option in self.options:
            if option['colour'] == 'green':
                string += f'<span class="badge bg-success">{option["label"]}</span> '
            elif option['colour'] == 'red':
                string += f'<span class="badge bg-danger">{option["label"]}</span> '
            elif option['colour'] == 'blurple':
                string += f'<span class="badge bg-primary">{option["label"]}</span> '
            else:
                string += f'<span class="badge bg-Secondary">{option["label"]}</span> '
        return string
    
    @property
    def character_count(self) -> int:
        count = 0
        for option in self.options:
            count += len(option['label'])
        return count

class Preset_Roles(Model):
    id = AutoField(primary_key=True)
    gid = ForeignKey(to=Config, on_delete=CASCADE, null=False, db_column='guild_id')
    preset = ForeignKey(to=Option_Presets, on_delete=CASCADE, null=False, db_column='preset_id')
    name = CharField(max_length=100, default="NONE")
    roles: list = JSONField(default=list, null=False)
    
    def __str__(self):
        return str(f'Preset Role {self.id}::{self.name}')
    
    @property
    def to_html(self) -> str:
        string = ""
        for role in self.roles:
            string += f'<span class="badge bg-success" aria-label="{role["role_id"]}">{role["role_name"]}</span> '
        return string
    
    @property
    def roles_to_string(self) -> str:
        string = ""
        for role in self.roles:
            string += f'{role["role_name"]}, '
        return string

from django.contrib.postgres.fields import ArrayField
class Templates(Model):
    id = AutoField(primary_key=True)
    gid = ForeignKey(to=Config, on_delete=CASCADE, null=False, db_column='guild_id')
    name = TextField(null=False)
    sheetid = TextField(null=True)
    worksheetid = BigIntegerField(null=True)
    cells: dict = JSONField(default=dict, null=False)
    lnkd_opt_presets = ArrayField(SmallIntegerField(null=False), null=False, default=list)
    
    title = TextField(null=True)
    description = TextField(null=True)
    
    thumb_url: str = TextField(null=True)
    emoji = TextField(null=True)
    
    ## Sheets Stuff
    sheet_client: gspread.Client = None
    
    def get_options(self) -> list[Option_Presets]:
        options: list[Option_Presets] = []
        for opt in self.lnkd_opt_presets:
            option = Option_Presets.objects.get(id=opt)
            if(option):
                options.append(option)
        
        return options
    
    def Config(self) -> Config:
        return self.gid
    
    @property
    def cell_title(self) -> str:
        return self.cells['cell_title'] if 'cell_title' in self.cells.keys() else 'None'
    @property
    def cell_desc(self) -> str:
        return self.cells['cell_desc'] if 'cell_desc' in self.cells.keys() else 'None'
    @property
    def cell_date(self) -> str:
        return self.cells['cell_date'] if 'cell_date' in self.cells.keys() else 'None'
    @property
    def cell_link(self) -> str:
        return self.cells['cell_link'] if 'cell_link' in self.cells.keys() else 'None'
    
    @property
    def presets_to_html(self) -> str:
        string = ""
        for option in self.lnkd_opt_presets:
            preset = Option_Presets.objects.get(id=option)
            
            string += f'<span class="badge bg-primary">{preset.name}</span> '
        return string
    
    def load_client(self):
        # Path to your service account credentials file
        credentials_file = GOOGLE_SERVICE_ACCOUNT_FILE
        # Define the scope for the API
        scope = ['https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive']

        # Authenticate using service account credentials
        try:
            creds = Credentials.from_service_account_file(credentials_file, scopes=scope)
            self.sheet_client = gspread.authorize(creds)
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e
    
    @property
    def hasSheetAccess(self) -> bool:
        if self.sheet_client is None:
            self.load_client()
        
        try:
            # Try to open the Google Sheet
            sheet = self.sheet_client.open_by_key(self.sheetid)
        except SpreadsheetNotFound:
            return False
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return False
        return True
    
    def get_cells_sets(self, preset_name: str) -> dict:
        sets = dict
        
        for option in self.cells[preset_name].keys():
            cell = self.cells[preset_name][option]
            
            if cell not in sets.keys():
                sets[cell] = []
            
            if option not in sets[cell]:
                sets[cell].append(option)
        
        return sets
    
    @property
    def thumb(self) -> str:
        return self.thumb_url if self.thumb_url != None and self.thumb_url.lower() != 'none' else None
            

class Events(ExportModelOperationsMixin('event'), Model):
    id = AutoField(primary_key=True)
    gid = ForeignKey(to=Config, on_delete=CASCADE, null=False, db_column='guild_id')

    message = BigIntegerField(null=True)
    channel = BigIntegerField()
    thread = BigIntegerField(null=True)

    data = JSONField(default=dict)
        
    option_preset = ForeignKey(to=Option_Presets, on_delete=SET_NULL, null=True)
    roleset = ForeignKey(to=Preset_Roles, on_delete=SET_NULL, null=True)
    template = ForeignKey(to=Templates, on_delete=SET_NULL, null=True)

    event_date = DateTimeField('date happening', auto_now=False, auto_now_add=False)
    tz = TextField(null=False, default="UTC")

    recurring_interval = SmallIntegerField(default=0) #This is in days 0 = Disabled
    recurring_until = DateTimeField(null=True) #Null = No End Date
    keep_signup_data = BooleanField(default=False)
    
    sentReminders = ArrayField(BooleanField(default=False, null=False), null=False, default=list)
    sentCheckin = BooleanField(default=False)
    
    calendar_event_id = TextField(default=None, null=True)

    delete_date = DateTimeField('deletion date', null=True)
    worksheet_id = TextField(null=True)
    sentCancelationMsg = BooleanField(default=False)
    
    author = BigIntegerField(null=True)

    created_date = DateTimeField(auto_now_add=True)
    edited_date = DateTimeField(auto_now=True)

    class Meta:
        ordering = ['event_date']
        
    def save(self, *args, **kwargs):
        is_new = True if not self.id else False
        super(Events, self).save(*args, **kwargs)
        if is_new:
            attendance = Attendance(id=self)
            attendance.save()
    
    async def async_delete(self):
        config: Config = await sync_to_async(self.Config)()
        now = arrow.Arrow.now().to('utc')
        
        if arrow.get(self.event_date).to('utc') < now:
            await sync_to_async(self.delete)()
        else: # Marked To Delete
            self.delete_date = now.shift(days=7).datetime
            await sync_to_async(self.save)()

    def __str__(self):
        return f'{self.data["title"]}'
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)
        
    def GetRoleset(self) -> Preset_Roles:
        return self.roleset
        
    def GetOptionPreset(self) -> Option_Presets:
        return self.option_preset
    
    def GetTemplate(self) -> Templates:
        return self.template
    
    def Config(self) -> Config:
        return self.gid
    
    @property
    def title_repr(self) -> str:
        return repr(self.data["title"])
    @property
    def title(self) -> str:
        return self.data["title"]
    @title.setter
    def title(self, value):
        self.data["title"] = value
        
    @property
    def date(self) -> datetime.datetime:
        return self.event_date.astimezone(TZ(self.tz))
    
    @property
    def date_str(self):
        return self.event_date.astimezone(TZ(self.tz)).strftime('%c')
    
    @property
    def date_arrow(self) -> arrow.Arrow:
        return arrow.get(self.event_date).to(TZ(self.tz))
    
    @property
    def date_discord(self):
        return f"<t:{int(self.event_date.timestamp())}:F>"
    
    @property
    def date_discord_relative(self):
        return f"<t:{int(self.event_date.timestamp())}:R>"

    @property
    def description_repr(self) -> str:
        return repr(self.data["description"])
    @property
    def description(self) -> str:
        return self.data["description"]
    @description.setter
    def description(self, value):
        self.data["description"] = value

    @property
    def capacity(self) -> int:
        return self.data["capacity"] if self.data["capacity"] != None else 0
    @capacity.setter
    def capacity(self, value):
        self.data["capacity"] = value
        
    @property
    def image(self) -> str:
        try:
            img = self.data["thumbImage"]
        except KeyError:
            img = None
        return img
    @image.setter
    def image(self, value):
        self.data["thumbImage"] = value
        
    @property
    def color(self) -> str:
        try:
            color = self.data["color"]
        except KeyError:
            color = "#f3df73"
        return color
    @color.setter
    def color(self, value):
        self.data["color"] = value
        
    @property
    def mentions(self) -> list[int]:
        return self.data["mentions"]
    @mentions.setter
    def mentions(self, value):
        self.data["mentions"] = value
        
    @property
    def recurring_until_str(self) -> str:
        return self.recurring_until.astimezone(TZ(self.tz)).strftime('%c') if self.recurring_until else None
    
    @property
    def was_published_recently(self) -> bool:
        now = timezone.now()
        return now - datetime.timedelta(days=7) <= self.created_date <= now

    @property
    def is_upcoming(self) -> bool:
        now = timezone.now()
        return now + datetime.timedelta(days=7) >= self.event_date >= now

    @property
    def isMarkedDelete(self) -> bool:
        return self.delete_date != None
    
    @property
    def inProgress(self) -> bool:
        now = timezone.now()
        return now + datetime.timedelta(hours=2) <= self.event_date <= now
    
    @property
    def responces(self) -> int:
        att: Attendance = Attendance.objects.get(id=self)
        responce_cnt = 0
        responce_cnt += (len(att.option_1) + len(att.option_2) + len(att.option_3) + 
                         len(att.option_4) + len(att.option_5) + len(att.option_6) + 
                         len(att.option_7) + len(att.option_8) + len(att.option_9))
        return responce_cnt
    
    def GetAttendance(self):
        att: Attendance = Attendance.objects.get(id=self)
        return att
    
    def author_name(self):
        try:
            user = DiscordUser.objects.get(id=self.author)
        except DiscordUser.DoesNotExist:
            return "Unknown"
        return user.name
    
    

class Events_Links(ExportModelOperationsMixin('linked_event'), Model):
    id = AutoField(primary_key=True)
    event_id = ForeignKey(to=Events, on_delete=CASCADE, null=False, db_column='event_id')
    linked_guild = ForeignKey(to=Config, on_delete=CASCADE, null=False, db_column='guild_id', default=1)
    
    message = BigIntegerField(null=False)
    channel = BigIntegerField(null=False)
    thread = BigIntegerField(null=False)

    calendar_event_id = TextField(default=None, null=True)
    
    sentReminders = ArrayField(BooleanField(default=False, null=False), null=False, default=list)
    sentCheckin = BooleanField(default=False)
    
    class Meta:
        ordering = ['id']
        constraints = [
            UniqueConstraint(
                fields=['event_id', 'linked_guild'], name='unique_attendance_combination'
            )
        ]

    
    def __str__(self):
        return f'Event Link:{self.linked_guild.id}:{self.event_id.id}'
    
    def save(self, *args, **kwargs):
        is_new = True if not self.id else False
        super(Events_Links, self).save(*args, **kwargs)
        if is_new:
            try:
                Attendance_Linked.objects.create(event=self, guild=self.linked_guild)
            except:
                logger.warning(f'{sys.exc_info()}')
    
    def Config(self) -> Config:
        return self.linked_guild
    
    def Event(self) -> Events:
        return self.event_id
    
    def GetAttendance(self):
        att: Attendance_Linked = Attendance_Linked.objects.get(event=self, guild=self.linked_guild)
        return att
    
    @property
    def title(self):
        return self.event_id.data["title"]
        
    @property
    def date(self) -> datetime.datetime:
        return self.event_id.event_date.astimezone(TZ(self.tz))
    
    @property
    def date_str(self):
        return self.event_id.event_date.astimezone(TZ(self.tz)).strftime('%c')

    @property
    def description_repr(self):
        return repr(self.event_id.data["description"])
    @property
    def description(self):
        return self.event_id.data["description"]


class Attendance(ExportModelOperationsMixin('attendance'), Model):
    id = ForeignKey(to=Events, on_delete=CASCADE, null=False, db_column='event_id', primary_key=True)
    guild = ForeignKey(to=Config, on_delete=CASCADE, null=False, default=1)
    
    attending = JSONField(default=list)
    declined = JSONField(default=list)
    tentative = JSONField(default=list)

    option_1 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_1')
    option_2 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_2')
    option_3 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_3')
    option_4 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_5 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_6 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_7 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_8 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_9 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    
    comfirmed = ArrayField(BigIntegerField(null=False), null=False, default=list)
    
    options = {
        SignupOption.Option_1: 'option_1',
        SignupOption.Option_2: 'option_2',
        SignupOption.Option_3: 'option_3',
        SignupOption.Option_4: 'option_4',
        SignupOption.Option_5: 'option_5',
        SignupOption.Option_6: 'option_6',
        SignupOption.Option_7: 'option_7',
        SignupOption.Option_8: 'option_8',
        SignupOption.Option_9: 'option_9',
    }
    
    def Config(self) -> Config:
        return self.guild
    
    def Event(self) -> Events:
        return self.id
    
    def reset_attendance(self):
        """Reset all attendance data for this event."""
        self.option_1 = []
        self.option_2 = []
        self.option_3 = []
        self.option_4 = []
        self.option_5 = []
        self.option_6 = []
        self.option_7 = []
        self.option_8 = []
        self.option_9 = []
        self.comfirmed = []
        self.save()
        
    def reset_confirmed(self):
        self.comfirmed = []
        self.save()
    
    def isAnySignupOption(self, user_id: int) -> bool:
        for option_field in self.options.values():
            if user_id in getattr(self, option_field):
                return True
        return False
    
    def isSignupOption(self, option: SignupOption, user_id: int) -> bool:
        option_field = self.options.get(option)
        if option_field:
            return user_id in getattr(self, option_field)
        return False
    
    def set_signup_option(self, option: SignupOption, user_id: int) -> None:
        option_field = self.options.get(option)
        if option_field:
            option_list = getattr(self, option_field)
            if user_id not in option_list:
                option_list.append(user_id)
                self.save()
    
    def remove_signup_option(self, option: SignupOption, user_id: int) -> None:
        option_field = self.options.get(option)
        if option_field:
            option_list = getattr(self, option_field)
            if user_id in option_list:
                option_list.remove(user_id)
                self.save()
    
    def get_signup_option(self, user_id: int) -> Optional[SignupOption]:
        for option in SignupOption:
            if user_id in getattr(self, self.options[option]):
                return option
        return None

    def get_signup_option_count(self, option: SignupOption) -> int:
        option_field = self.options.get(option)
        if option_field:
            return len(getattr(self, option_field))
        return -1

    def get_signup_option_list(self, option: SignupOption) -> list[int]:
        option_field = self.options.get(option)
        if option_field:
            return getattr(self, option_field)
        return []

    def get_signup_counts_data(self) -> list[tuple[str, int]]:
        data: list[tuple[str, int]] = list(tuple())
        for option in SignupOption:
            count = self.get_signup_option_count(option)
            data.append((option.name, count))
        return data
    
    def isConfirmed(self, user_id: int) -> bool:
        return user_id in self.comfirmed
    
    def remove_confirmed(self, user_id: int) -> None:
        if user_id in self.comfirmed:
            self.comfirmed.remove(user_id)
            self.save()
            
    def set_confirmed(self, user_id: int) -> None:
        if user_id not in self.comfirmed:
            self.comfirmed.append(user_id)
            self.save()
    
    def get_confirmed_count(self) -> int:
        return len(self.comfirmed)

    def get_confirmed(self) -> list[int]:
        return self.comfirmed
    
    def get_all_responses(self) -> list[int]:
        return list(set(self.option_1 + self.option_2 + self.option_3 + self.option_4 + self.option_5 + self.option_6 + self.option_7 + self.option_8 + self.option_9))

class Attendance_Linked(ExportModelOperationsMixin('linked attendance'), Model):
    event = ForeignKey(to=Events_Links, on_delete=CASCADE, null=False)
    guild = ForeignKey(to=Config, on_delete=CASCADE, null=False)
    
    option_1 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_1')
    option_2 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_2')
    option_3 = ArrayField(BigIntegerField(null=False), null=False, default=list, db_column='option_3')
    option_4 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_5 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_6 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_7 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_8 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    option_9 = ArrayField(BigIntegerField(null=False), null=False, default=list)
    
    comfirmed = ArrayField(BigIntegerField(null=False), null=False, default=list)
    
    options = {
        SignupOption.Option_1: 'option_1',
        SignupOption.Option_2: 'option_2',
        SignupOption.Option_3: 'option_3',
        SignupOption.Option_4: 'option_4',
        SignupOption.Option_5: 'option_5',
        SignupOption.Option_6: 'option_6',
        SignupOption.Option_7: 'option_7',
        SignupOption.Option_8: 'option_8',
        SignupOption.Option_9: 'option_9',
    }
    
    def Config(self) -> Config:
        return self.guild
    
    def Event(self) -> Events:
        return self.event
    
    def reset_attendance(self):
        """Reset all attendance data for this linked event."""
        self.option_1 = []
        self.option_2 = []
        self.option_3 = []
        self.option_4 = []
        self.option_5 = []
        self.option_6 = []
        self.option_7 = []
        self.option_8 = []
        self.option_9 = []
        self.comfirmed = []
        self.save()
        
    def reset_confirmed(self):
        self.comfirmed = []
        self.save()
    
    def isAnySignupOption(self, user_id: int) -> bool:
        for option_field in self.options.values():
            if user_id in getattr(self, option_field):
                return True
        return False
    
    def isSignupOption(self, option: SignupOption, user_id: int) -> bool:
        option_field = self.options.get(option)
        if option_field:
            return user_id in getattr(self, option_field)
        return False
    
    def set_signup_option(self, option: SignupOption, user_id: int) -> None:
        option_field = self.options.get(option)
        if option_field:
            option_list = getattr(self, option_field)
            if user_id not in option_list:
                option_list.append(user_id)
                self.save()
    
    def remove_signup_option(self, option: SignupOption, user_id: int) -> None:
        option_field = self.options.get(option)
        if option_field:
            option_list = getattr(self, option_field)
            if user_id in option_list:
                option_list.remove(user_id)
                self.save()
    
    def get_signup_option(self, user_id: int) -> Optional[SignupOption]:
        for option in SignupOption:
            if user_id in getattr(self, self.options[option]):
                return option
        return None

    def get_signup_option_count(self, option: SignupOption) -> int:
        option_field = self.options.get(option)
        if option_field:
            return len(getattr(self, option_field))
        return -1

    def get_signup_option_list(self, option: SignupOption) -> list[int]:
        option_field = self.options.get(option)
        if option_field:
            return getattr(self, option_field)
        return []

    def get_signup_counts_data(self) -> list[tuple[str, int]]:
        data: list[tuple[str, int]] = list(tuple())
        for option in SignupOption:
            count = self.get_signup_option_count(option)
            data.append((option.name, count))
        return data
    
    def isConfirmed(self, user_id: int) -> bool:
        return user_id in self.comfirmed
    
    def remove_confirmed(self, user_id: int) -> None:
        if user_id in self.comfirmed:
            self.comfirmed.remove(user_id)
            self.save()
            
    def set_confirmed(self, user_id: int) -> None:
        if user_id not in self.comfirmed:
            self.comfirmed.append(user_id)
            self.save()
            
    def get_confirmed_count(self) -> int:
        return len(self.comfirmed)

    def get_confirmed(self) -> list[int]:
        return self.comfirmed
    
    def get_all_responses(self) -> list[int]:
        return list(set(self.option_1 + self.option_2 + self.option_3 + self.option_4 + self.option_5 + self.option_6 + self.option_7 + self.option_8 + self.option_9))


class Stats_Created(Model):
    gid = BigIntegerField(null=False, db_column='gid')
    author = BigIntegerField()
    web = BooleanField(default=False)
    date = DateTimeField(auto_now_add=True)

    def isXDate(self, days:int):
        date = timezone.now() - datetime.timedelta(days=days)
        return date.date() == self.date.date()

class Stats_Edited(Model):
    gid = BigIntegerField(null=False, db_column='gid')
    author = BigIntegerField(null=True)
    web = BooleanField(default=False)
    date = DateTimeField(auto_now_add=True)

    def isXDate(self, days:int):
        date = timezone.now() - datetime.timedelta(days=days)
        return date.date() == self.date.date()

class Stats_Deleted(Model):
    gid = BigIntegerField(null=False, db_column='gid')
    author = BigIntegerField(null=True)
    web = BooleanField(default=False)
    date = DateTimeField(auto_now_add=True)

    def isXDate(self, days:int):
        date = timezone.now() - datetime.timedelta(days=days)
        return date.date() == self.date.date()
    
class Stats_Join(Model):
    date = DateTimeField(auto_now_add=True)

    def isXDate(self, days:int):
        date = timezone.now() - datetime.timedelta(days=days)
        return date.date() == self.date.date()

class Stats_Leave(Model):
    date = DateTimeField(auto_now_add=True)

    def isXDate(self, days:int):
        date = timezone.now() - datetime.timedelta(days=days)
        return date.date() == self.date.date()

class Stats_Responded(Model):
    gid = BigIntegerField(null=False, db_column='gid')
    date = DateTimeField(auto_now_add=True)
    hours_after = SmallIntegerField(null=False)
    user_id = BigIntegerField(null=False)
    event_id = BigIntegerField(null=False)


class Blog(Model):
    POST_TYPE_CHOICES = [
        ('news', 'News'),
        ('changelog', 'Changelog'),
    ]
    
    title = CharField(max_length=200)
    slug = SlugField(max_length=200, unique=True)
    content = TextField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    author = BigIntegerField()
    featured_image = ImageField(upload_to='blog_images/', null=True, blank=True)
    is_published = BooleanField(default=False)
    post_type = CharField(max_length=20, choices=POST_TYPE_CHOICES, default='news')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_author_name(self):
        try:
            from discord.models import User
            user = User.objects.get(id=self.author)
            return user.discord_tag
        except User.DoesNotExist:
            return "Unknown"
    
class CommandAnalytics(Model):
    gguild = BigIntegerField(null=False)
    date = DateTimeField(auto_now_add=True)
    command = TextField(null=False)
    user_id = BigIntegerField(null=False)
    stage = TextField(null=True)
    success = BooleanField(null=False)
    error = TextField(null=True)
    


