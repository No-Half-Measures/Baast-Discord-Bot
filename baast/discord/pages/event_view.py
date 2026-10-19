import sys
from datetime import datetime, timedelta
import pytz
import asyncio
import logging
import time as Time
import dateutil.parser

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, redirect
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse

from gspread import Worksheet

from hikari import RESTApp, UnauthorizedError, OwnUser, NotFoundError

from channels.layers import get_channel_layer

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles
from discord.hashids import Hashids

from cache.helpers import GetUser
from cache.models import DiscordChannel, DiscordGuild, DiscordUser

from app.models import Events, Events_Links, Config, Attendance, Attendance_Linked, Templates, Option_Presets, Preset_Roles, Stats_Created, Stats_Edited

from bot.bot.utils.enums import SignupOption
from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.modules.events.classes.calendar import Calendar

from loguru import logger


class EventView(GuildMixin, View):
    template_name = 'discord/dash_event.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return async_to_sync(view)

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        guild_data, error_response = await self.validate_guild_request(request, kwargs)
        if error_response:
            return error_response
        
        event_id = int(kwargs['id'])
        
        event: Events = None
        event_linked: Events_Links = None
        
        try:
            if request.path.__contains__('/linked/'):
                event_linked: Events_Links = await sync_to_async(Events_Links.objects.get)(linked_guild=guild_data.config, id=event_id)
                event: Events = await sync_to_async(event_linked.Event)()
            else:  
                event: Events = await sync_to_async(Events.objects.get)(gid=guild_data.config, id=event_id)
        except Exception as e:
            logger.error(f'Error fetching event: {e}')
            return JsonResponse({"error": "Error fetching event"}, status=500)
        

        attending_users = await self.getAttending(guild_data.guild_id, event, linked_event=event_linked)
        
        channels: list[DiscordChannel] = await Channels.get(guild_data.guild_id)
        roles = await Roles.get(guild_data.guild_id)
        
        
        attendance: Attendance | Attendance_Linked = await sync_to_async(event.GetAttendance if event_linked == None else event_linked.GetAttendance)()
        data = attendance.get_signup_counts_data()
        preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        
        count_data: list[tuple[str, int]] = list(tuple())
        for i, option in enumerate(preset.options):
            count_data.append((option["label"], data[i][1]))
            
        sentReminders = {}
        
        for i, reminder in enumerate(guild_data.config.reminders):
            if event_linked == None:
                sentReminders[reminder["name"]] = event.sentReminders[i]
            else:
                sentReminders[reminder["name"]] = event_linked.sentReminders[i]
                
        context = {
            "channels": channels,
            "roles": roles,
            
            "option_counts": count_data,
            "event" : event,
            "attending_users": attending_users ,
            "sentReminders": sentReminders,
            "sentCheckin": event.sentCheckin if event_linked == None else event_linked.sentCheckin,
            "is_linked_event": request.path.__contains__('/linked/'),
            
            "discord_url": f"https://discord.com/channels/{guild_data.guild_id}/{event.channel if event_linked == None else event_linked.channel}/{event.message if event_linked == None else event_linked.message}",
            
            "timezones" : pytz.all_timezones,
        }
        
        return await sync_to_async(render)(request, self.template_name, context)
    
    async def getEvent(self, event_id:int):
        if await sync_to_async(cache.get)(event_id):
            event: Events = await sync_to_async(cache.get)(event_id)

            utc = pytz.UTC
            now = utc.localize( datetime.utcnow())
            period = now - timedelta(minutes=CACHE_TTL)
            
            try:
                await sync_to_async(Events.objects.get)(id=event_id, edited_date__gte=period)
            except Events.DoesNotExist:
                print()
            else:
                try:
                    await sync_to_async(Events.objects.get)(id=event_id, edited_date__exact=event.edited_date)
                except Events.DoesNotExist:
                    event = await sync_to_async(Events.objects.get)(id=event_id)
                    await sync_to_async(cache.set)(event_id, event)
        else:
            try:
                event = await sync_to_async(Events.objects.get)(id=event_id)
                await sync_to_async(cache.set)(event_id, event)
            except Events.DoesNotExist:
                return None
        
        return event

    async def getAttending(self, guild_id: str, event:Events, linked_event: Events_Links = None):
        attending: dict = {}
        
        attendance: Attendance | Attendance_Linked = None
        
        if linked_event is None:
            try:
                attendance: Attendance = await sync_to_async(event.GetAttendance)()
            except Attendance.DoesNotExist:
                logger.warning(f'Event {event.id} is missing its attendance node.')
                return None
        else:
            try:
                attendance: Attendance_Linked = await sync_to_async(linked_event.GetAttendance)()
            except Attendance_Linked.DoesNotExist:
                logger.warning(f'Linked Event {linked_event.id} is missing its attendance node.')
                return None
                
                
        preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        
        #"label": "Hard Support", "istentative": False, "send_notifcations": True
        mentions = ""
        for i, option in enumerate(preset.options):
            if option["send_notifcations"] == True and option["istentative"] == False:
                attending[str(option["label"])] = {"id": i, "users":[]}
                
                signups = attendance.get_signup_option_list(SignupOption(i))
                users_str = 'None'
                if signups:
                    usrs, users_str = await self.build_users(guild_id, signups)
                    mentions += users_str
            
                    for u in usrs:
                        attending[str(option["label"])]["users"].append({"id": u.id,"name": f"{u.name}"})
        
        return attending
    

    async def post(self, request: HttpRequest, *args, **kwargs):
        guild_data, error_response = await self.validate_guild_request(request, kwargs)
        if error_response:
            return error_response

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax and request.method == "POST":
            event_id = int(kwargs['id'])
            
            restapp = await self.get_restapp(guild_data.access_token)
            try:
                async with restapp.acquire(guild_data.access_token, "BEARER") as bearer:
                    author: OwnUser = await bearer.fetch_my_user()
            finally:
                await self.release_restapp(guild_data.access_token, restapp)
            

            # Get Data and break it down
            data = request.POST.dict()
            
            title = data['title']
            description = data['desc']
            capacity = data['cap']
            channel = data['channel']
            date = data['date']
            time = data['time']
            tz = data['tz']
            color = data['color']
            recurring_interval = int(data['recurring_interval'])
            recurring_until = data['recurring_until']
            
            # Validation
            # Check title length
            if len(title) == 0:
                return JsonResponse({"error": "Event title is blank! Try Again..."}, status=400)
            if len(title) > 200:
                return JsonResponse({"error": "Event title is too long! Try Again..."}, status=400)
            
            # Get Template
            template: Templates = None
            if data['template'] != 'undefined':
                try:
                    template: Templates = await sync_to_async(Templates.objects.get)(id=data['template'])
                except Templates.DoesNotExist:
                    template = None
            
            # Get Options
            options: Option_Presets = None
            if data['option'] != 'undefined':
                try:
                    options: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=data['option'])
                except Option_Presets.DoesNotExist:
                    options = None
                    
            # Get Roleset
            roleset: Preset_Roles = None
            if data['roleset'] not in ['undefined', 'null']:
                try:
                    roleset: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id=data['roleset'])
                except Preset_Roles.DoesNotExist:
                    roleset = None
            
            # Date/Time (y/m/d)
            date = date.split('-')
            time = time.split(':')
            
            recurring_date = recurring_until.split('-')
            
            d = None
            recurring_d = None
            
            
            if (not self.is_valid_datetime(date, time)):
                return JsonResponse({"error": "Event Date and/or Time is invalid! Try Again..."}, status=400)
            else:
                d = datetime(int(date[0]), int(date[1]), int(date[2]), hour=int(time[0]), minute=int(time[1]), tzinfo=dateutil.tz.gettz(tz))
                
                if d < datetime.now(pytz.UTC):
                    return JsonResponse({"error": "Event Date/Time can not be in the past! Try Again..."}, status=400)
            
            if recurring_until != 'null':
                if (not self.is_valid_datetime(recurring_date, ['0', '0'])):
                    return JsonResponse({"error": "Recurring Until Date is invalid! Try Again..."}, status=400)
                else:
                    recurring_d = datetime(int(recurring_date[0]), int(recurring_date[1]), int(recurring_date[2]), hour=0, minute=0)
            
            if event_id == -1:
                try:
                    return await self.create_event(request, guild_data.guild_hash, guild_data.guild_id, author, title, description, d, capacity, template, options, roleset, channel, data['mentions'].split(','), color, recurring_interval, recurring_d)
                except:
                    logger.error(f'Error Creating Event:\n {sys._getframe()}:{sys.exc_info()}')
            else:
                return await self.edit_event(request, guild_data.guild_hash, guild_data.guild_id, event_id, author, title, description, d, capacity, channel, color, recurring_interval, recurring_d)
        
        return JsonResponse({"error": "Unkown Error"}, status=400)


    async def build_users(self, guild_id: int, user_ids: list[int]) -> tuple[list[DiscordUser], str]:
        users: list[DiscordUser] = list()
        string = ''
        for id in user_ids:
            cachedUser: DiscordUser = None
            timeout = 1   # [seconds]
            timeout_start = Time.time()

            while Time.time() < timeout_start + timeout and cachedUser is None:
                try:
                    cachedUser = await sync_to_async(GetUser)(id)
                except DiscordUser.DoesNotExist:
                    channel_layer = get_channel_layer()
                    await channel_layer.send('discord', {'type': 'get.user', 'g_id': str(guild_id), 'u_id': str(id)})
                    Time.sleep(0.5)
            
            if cachedUser != None:
                users.append(cachedUser)
                string += f'{cachedUser.mention}\n'
            
        return users, string

    def is_valid_datetime(self, date: list[str], time: list[str]) -> bool:
        try:
            d = datetime(int(date[0]), int(date[1]), int(date[2]), hour=int(time[0]), minute=int(time[1]), tzinfo=pytz.UTC)
        except:
            return False
        return True

    
    async def create_event(self, request: HttpRequest, guild_hash:str, guild_id: str, author: OwnUser, title: str, description: str, dateTime: datetime, 
                            capacity: int, template: Templates, options: Option_Presets, roleset: Preset_Roles, channel_id: str, mentions_arr, color: str,
                            recurring_interval: int, recurring_until: datetime):
        
        conf: Config = await sync_to_async(Config.objects.get)(guild=guild_id)
        
        now = datetime.utcnow().astimezone(pytz.UTC)
        
        reminderFlags = []
        for r in conf.reminders:
            evdate = dateTime
            if r['sequence'] == 'before':
                evdate = evdate - timedelta(hours=r['time'])
            else:
                evdate = evdate + timedelta(hours=r['time'])
            
            reminderFlags.append(evdate >= now if r['sequence'] == 'before' else evdate <= now)
            
        
        event: Events = await sync_to_async(Events.objects.create)(
            gid = conf,
            
            message = None,
            channel = channel_id,
            thread = None,
            
            event_date=dateTime,
            tz= dateTime.tzname() if dateTime.tzname() != 'LMT' else Time.tzname[0] if Time.tzname[0] != 'GMT Standard Time' else 'GMT',
            data = {
                'title': title,
                'description': description,
                'capacity': capacity,
                "thumbImage": None,
                "color": color,
            },
            template = template,
            option_preset= options,
            roleset = roleset,
            
            sentReminders = reminderFlags,
            
            author = author.id,
            
            recurring_interval = recurring_interval,
            recurring_until = recurring_until,
        )
        
        if not event:
            return JsonResponse({"error": "Failed to creat event..."}, status=400)
        
        ## SEND CHANNNEL EVENT POST_EVENT
        channel_layer = get_channel_layer()
        await channel_layer.send('discord', {'type': 'post.event', 
                                             'id': event.id,
                                             'user_id': int(author.id),
                                             'mentions': mentions_arr,
                                             })
        
        await sync_to_async(Stats_Created.objects.create)(gid=conf.id, author=int(author.id), web=True)
        
        return JsonResponse({"redirect": f"{'https://' if request.is_secure() else 'http://'}{request.get_host()}{reverse('discord:dash_event', kwargs={'hashguild':guild_hash, 'id':event.id})}"}, status=200)

    async def edit_event(self, request: HttpRequest, guild_hash:str, guild_id: str, event_id: str, author: OwnUser, title: str, description: str, 
                         dateTime: datetime, capacity: int, channel_id: str, color: str, recurring_interval: int, recurring_until: datetime):
        conf: Config = await sync_to_async(Config.objects.get)(guild=guild_id)
        
        try:
            event: Events = await sync_to_async(Events.objects.get)(gid=conf, id=event_id)
        except Events.DoesNotExist:
            return JsonResponse({"error": "Null Event"}, status=400)

        if not event:
            logger.warning(f'No Event\n{sys.exc_info()}')
            return JsonResponse({"error": "Null Event"}, status=400)
        
        visualChange = (event.title == title and event.description == description and event.capacity == int(capacity) and event.event_date == dateTime
                        and event.recurring_interval == recurring_interval and event.recurring_until == recurring_until)
        
        if visualChange:
            return JsonResponse({"error": "No changes made"}, status=400)
        
        
        edits: list[int] = list()
        if event.title != title:
            event.title = title if len(title) <= 200  else title[:200]
            if not event.isMarkedDelete:
                edits.append(1)
        

        if event.description != description:
            event.description = description if len(description) <= 1600  else description[:1600]
            if not event.isMarkedDelete:
                edits.append(2)
        

        if event.capacity != int(capacity):
            event.capacity = int(capacity) if int(capacity) <= 100 else 100
            if not event.isMarkedDelete:
                edits.append(4)
        

        if event.event_date != dateTime:
            event.event_date = dateTime
            if not event.isMarkedDelete:
                edits.append(3)

        if event.tz != dateTime.tzname():
            event.tz=dateTime.tzname() if dateTime.tzname() != 'LMT' else (Time.tzname[0] if Time.tzname[0] != 'GMT Standard Time' else 'GMT')
            
        if event.color != color:
            event.color = color
        
        if event.recurring_interval != recurring_interval:
            event.recurring_interval = recurring_interval
        
        if event.recurring_until != recurring_until:
            event.recurring_until = recurring_until
        
        try:
            await event.asave()
        except:
            logger.error('Failed to save event.')
            return JsonResponse({"error": "Error failed to save event."}, status=400)
        
        
        ##Sheet
        sheets = None
        if conf.is_premium and event.worksheet_id != None:
            try:
                cache:DiscordGuild = await sync_to_async(DiscordGuild.objects.get)(discord_id=conf.guild)
            except Exception as e:
                logger.warning(e)
            
            try:
                sheets = Sheet(conf, cache.discord_name, event)
            except:
                logger.error(sys.exc_info())
            else:
                template: Templates = await sync_to_async(event.GetTemplate)()
                for e in edits:
                    if e == 1:
                        await sheets.UpdateTitle(event.title, event.date_arrow, template)
                    elif e == 2:
                        await sheets.UpdateDescription(event.description, template)
                    elif e == 3:
                        await sheets.UpdateDate(event.date_arrow, template)
                    elif e == 4:
                        await sheets.UpdateCapacity(event.capacity, await sync_to_async(event.GetOptionPreset)(), template)
                    elif e == 5:
                        await sheets.UpdateAttendance(event)
        
        ## Google Calendar
        if conf.calendar_enabled and event.calendar_event_id != None and conf.is_premium:     
            try:
                cal: Calendar = Calendar()
            except:
                logger.error(sys.exc_info())
            else:   
                try:
                    await sync_to_async(cal.edit_event)(event, conf)
                except:
                    logger.error(sys.exc_info())
        
        if not event.isMarkedDelete:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.send('discord', {'type': 'update.event', 'id': event.id, 'edits': edits, 'user_id': author.id})
            
            await sync_to_async(Stats_Edited.objects.create)(gid=conf.id, author=int(author.id), web=True)

        return JsonResponse({"redirect": f"{'https://' if request.is_secure() else 'http://'}{request.get_host()}{reverse('discord:dash_event', kwargs={'hashguild':guild_hash, 'id':event.id})}"}, status=200)

