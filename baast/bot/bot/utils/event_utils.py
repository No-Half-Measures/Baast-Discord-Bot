import asyncio
from calendar import Calendar
import sys
from asyncio import TimeoutError
from asgiref.sync import async_to_sync, sync_to_async
import hikari
from loguru import logger
import datetime
from pytz import timezone as TZ
import arrow

from django.conf import settings
from django.db.models import QuerySet

from discord.hashids import Hashids

from hikari import (Emoji, PartialInteraction, MessageFlag, TextInputStyle, ButtonStyle, Message, Embed, Color, Role, 
                    ComponentInteraction, Member, Guild, User, ActionRowComponent, TextableChannel, GuildPrivateThread, GuildThreadChannel,
                    Snowflakeish, MESSAGE_RESPONSE_TYPES)
from hikari.api import RESTClient
from hikari.api.special_endpoints import MessageActionRowBuilder
from hikari.errors import NotFoundError
from lightbulb import Context, Client

from app.models import Attendance_Linked, Stats_Created, Templates, Option_Presets, Config, Events, Attendance, Events_Links, Preset_Roles

from bot.bot.components import TemplateSelect, OptionPresetSelect, EventSelect, RolePresetSelect
from bot.bot.components.event_builder import EventBuilder
from bot.bot.components.support_button import SupportButton
from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.enums import SignupOption
from bot.bot.utils.util import validate_datetime
from bot.bot.utils.exceptions import DatetimeError, SetupCancel, NoValues
from bot.bot.utils.discord_utils import GetChannels


salt = "HASH_SALT_HERE"
IS_LOCAL = getattr(settings, 'LOCAL')

buttonNames = ['bastEvAccept', 'bastEvDecline', 'bastEvTentative', 'bastOption_4', 'bastOption_5', 'bastOption_6', 'bastOption_7', 'bastOption_8', 'bastOption_9']
manageButtonNames = ['bastEvUser', 'bastEvEdit', 'bastEvDelete']

embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the command timedout.',
    color = Color(0xff0000)
)
embedCancel = Embed(
    title = None,
    description = 'You cancelled the command.',
    color = Color(0xff0000)
)

class EventCreateException(Exception):
    def __init__(self,msg):
        self.msg=msg
        print( 'event creation exception occurred')


def isNumber(value: str) -> bool:
    try:
        val = int(value)
    except ValueError:
        return False
    return True

def roles_to_string(mentions: list[Role]) -> tuple[str, bool]:
    mentionStr = ''
    everyone = False
        
    if mentions:
        for m in mentions:
            if m.name == '@everyone':
                everyone = True
                mentionStr += f'@everyone '
            else:
                mentionStr += f'{m.mention} '

    return mentionStr, everyone

def build_users(guild: Guild, user_ids: list[int], confirmed: list[int] = None) -> tuple[list[Member], str]:
    users = list()
    string = ''
    
    for id in user_ids:
        u = guild.get_member(id)
        users.append(u)
        string += f"{u.mention}{'<:confirmed:1225137293581615176>' if id in confirmed else ''}\n"
        
    return users, string

async def build_users_split(guild: Guild, user_ids: list[int], confirmed: list[int] = None) -> dict:
    users = []
    string = []
    
    for id in user_ids:
        u: (Member | None) = guild.get_member(id)
        
        if u:
            users.append(u)
            string.append(f"{u.mention}{'<:confirmed:1225137293581615176>' if id in confirmed else ''}\n")
        else:
            try:
                u = await guild.app.rest.fetch_member(guild.id, id)
            except NotFoundError:
                users.append(None)
                string.append(f"<@{id}>{'<:confirmed:1225137293581615176>' if id in confirmed else ''}\n")
                continue
            except:
                logger.error(sys.exc_info())
                continue
            else:
                users.append(u)
                string.append(f"{u.mention}{'<:confirmed:1225137293581615176>' if id in confirmed else ''}\n")
    
        
    return { "guild": guild.name, "users": users, "user_strings": string }


#
#
#
#

async def GetEvent(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, events: list[Events], title:str = None) -> Events:
    try:
        selectObj:EventSelect = await EventSelect().create(ctx, events, snowflake, title=title)
        await ctx.edit_response(snowflake, selectObj.embed, components=selectObj)
    except NoValues:
        logger.warning(f'No Event Selected!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except SetupCancel:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        event: Events = await sync_to_async(Events.objects.get)(id = selectObj.selected_events[0])
    except Events.DoesNotExist:
        logger.warning(f'User selected a event that no longer exists : `{selectObj.selected_events[0]}`.')
        return None
    except:
        logger.error(sys.exc_info())
        return None
        
    return event

async def GetTemplate(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish) -> Templates:
    try:
        selectObj:TemplateSelect = await TemplateSelect().create(ctx, snowflake)
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=selectObj.embed, components=selectObj)
        else:
            await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
    except NoValues:
        logger.warning(f'No Template Selected!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    
    try:
        template = await sync_to_async(Templates.objects.get)(id = selectObj.selected)
    except Templates.DoesNotExist:
        logger.warning(f'User Selected a Template that no longer exists : {selectObj.selected}.')
        return None
    except:
        logger.error(sys.exc_info())
        return None
    
    return template

async def GetSignupOptions(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, template: Templates) -> Option_Presets:
    try:
        selectObj:OptionPresetSelect = await OptionPresetSelect().create(ctx, template, snowflake)
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=selectObj.embed, components=selectObj)
        else:
            await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
    except NoValues:
        logger.warning(f'No Option Preset Selected!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    
    try:
        option_preset: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id = selectObj.selected)
    except Option_Presets.DoesNotExist:
        logger.warning(f'User Selected a Option Preset that no longer exists : {selectObj.selected}.')
        return None
    except:
        logger.error(sys.exc_info())
        return None
        
    return option_preset

async def GetRoleset(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, option_preset: Option_Presets) -> Preset_Roles:
    try:
        selectObj:RolePresetSelect = await RolePresetSelect().create(ctx, option_preset, snowflake)
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=selectObj.embed, components=selectObj)
        else:
            await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
    except NoValues:
        logger.warning(f'No Role Preset Selected!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    
    if selectObj.selected == None:
        return None
    
    try:
        role_preset: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id = selectObj.selected)
    except Preset_Roles.DoesNotExist:
        logger.warning(f'User Selected a Role Preset that no longer exists : {selectObj.selected}.')
        return None
    except:
        logger.error(sys.exc_info())
        return None
        
    return role_preset

async def RunEventBuilder(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, 
                          template: Templates, options_preset: Option_Presets, user: User, event: Events = None,
                          reccuring_events_count: int = 0) -> tuple[dict, arrow.Arrow, int, arrow.Arrow, bool, list[Role]]:
    try:
        selectObj:EventBuilder = EventBuilder(snowflake, template, options_preset)
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.create(ctx, user,
                        title=event.title if event else template.title,  
                        description=event.description if event else template.description, 
                        capacity=event.capacity if event else 100, 
                        thumb=event.image if event else None, 
                        dateTime=arrow.Arrow.fromdatetime(event.date, TZ(event.tz)) if event else arrow.utcnow(), 
                        recurring_interval=event.recurring_interval if event else 0, 
                        recurring_until=arrow.Arrow.fromdatetime(event.recurring_until, TZ(event.tz)) if event and event.recurring_until else None, 
                        keep_signup_data=event.keep_signup_data if event else False,
                        color=event.color if event else '#f3df73')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        if type(ctx) == ComponentInteraction:
            await ctx.edit_initial_response(selectObj.embed, components=selectObj)
        else:
            await ctx.edit_response(snowflake, selectObj.embed, components=selectObj)
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except asyncio.TimeoutError:
        if type(ctx) == ComponentInteraction:
            await ctx.edit_initial_response(embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        raise SetupCancel
        
    return {"title": selectObj.title, 
            "description": selectObj.description, 
            "capacity": selectObj.capacity, 
            "thumbImage": selectObj.thumbnail,
            "color": selectObj.color,
            }, selectObj.date, selectObj.recurring_interval, selectObj.recurring_until, selectObj.keep_signup_data, selectObj.mentions


async def UpdateEvent(ctx: Context | ComponentInteraction, client: Client, config: Config, event: Events, option_preset: Option_Presets, 
                      data: dict, date: arrow.Arrow, recuringInterval: int, recuringUntil: arrow.Arrow, keep_signup_data: bool, user: User) -> (
                          tuple[list[Embed], list[ActionRowComponent], Events, list[Embed], list[Embed]]):
    logs: list[Embed] = []
    thread_logs: list[Embed] = []
    sheets = None
    template = await sync_to_async(event.GetTemplate)()
    
    if config.is_premium:
        try:
            sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name, event)
        except:
            logger.error(sys.exc_info())
    
    if config.logs_enabled:
        if data['title'] != event.title:
            if config.is_premium and sheets != None and template != None:
                await sheets.UpdateTitle(data['title'], date, template)
            
            thread_logs.append(Embed(description=f"Title Changed from `{event.title}` to `{data['title']}`"))
        
        if data['description'] != event.description:
            if config.is_premium and sheets != None and template != None:
                await sheets.UpdateDescription(data['description'], template)
            
            thread_logs.append(Embed(description=f"Description Changed from `{event.description}` to `{data['description']}`"))
            
        if data['capacity'] != event.capacity:
            if config.is_premium and sheets != None and template != None:
                await sheets.UpdateCapacity(data['capacity'], option_preset, template)
            
            logs.append(Embed(description=f"Capacity Changed from `{event.capacity}` to `{data['capacity']}`"))
        
        if data['thumbImage'] != event.image:
            logs.append(Embed(description=f"Thumbnail Changed from `{event.image}` to `{data['thumbImage']}`"))
        
        if data['color'] != event.color:
            logs.append(Embed(description=f"Color Changed from `{event.color}` to `{data['color']}`"))
        
        if date.datetime != event.event_date:
            if config.is_premium and sheets != None and template != None:
                await sheets.UpdateDate(date, template)
            
            thread_logs.append(Embed(description=f"Date Changed from <t:{int(event.event_date.timestamp())}:F> to <t:{int(date.to('utc').datetime.timestamp())}:F>"))
            
        if recuringInterval != event.recurring_interval or recuringUntil != event.recurring_until:
            if recuringInterval % 7 == 0:
                weeks = recuringInterval // 7
                recurrence_text = f"\n**Recurring**: Every {weeks} week{'s' if weeks > 1 else ''}"
            else:
                recurrence_text = f"\n**Recurring**: Every {recuringInterval} day{'s' if recuringInterval > 1 else ''}"

            if recuringUntil:
                recurrence_text += f" until <t:{int(arrow.get(recuringUntil).to('utc').datetime.timestamp())}:D>"
            ##
            if event.recurring_interval % 7 == 0:
                weeks = event.recurring_interval // 7
                old_recurrence_text = f"\n**Recurring**: Every {weeks} week{'s' if weeks > 1 else ''}"
            else:
                old_recurrence_text = f"\n**Recurring**: Every {event.recurring_interval} day{'s' if event.recurring_interval > 1 else ''}"

            if event.recurring_until:
                old_recurrence_text += f" until <t:{int(arrow.get(event.recurring_until).to('utc').datetime.timestamp())}:D>"
                
            logs.append(Embed(description=f"Recurring Changed from `{old_recurrence_text}` to {recurrence_text}"))
    
    event.data = data
    event.event_date = date.datetime
    event.recurring_interval = recuringInterval
    event.recurring_until = recuringUntil.datetime if recuringUntil else None
    event.keep_signup_data = keep_signup_data
    
    embeds = await RebuildEventEmbed(client.rest, event, await sync_to_async(event.GetAttendance)())
    componentRow = await BuildComponents(client.rest, config, option_preset, event.date_arrow)
    
    await event.asave()
    
    return embeds, componentRow, event, thread_logs + logs, thread_logs


async def CreateEvent(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, config: Config, event: Events = None) -> tuple[Events, Message]:
    # VARS
    data: dict = {}
    date: arrow.Arrow = arrow.utcnow()
    mentions: list[Role] = []
    
    try:
        channel = await GetChannels(ctx, client, snowflake, max=1, fav_channels=config.event_channels)
    except NoValues:
        await ctx.edit_response(snowflake, content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `SEND_MESSAGES`, `SEND_MESSAGES_IN_THREADS`, `VIEW_CHANNEL`, `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, `MANAGE_THREADS`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
        raise NoValues
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        template = await GetTemplate(ctx, client, snowflake)
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        option_preset = await GetSignupOptions(ctx, client, snowflake, template)
    except:
        logger.error(sys.exc_info())
        return
    
    #
    # START Builder
    #
    try:
        data, date, recuringInterval, recuringUntil, keep_signup_data, mentions = await RunEventBuilder(ctx, client, snowflake, template, option_preset, 
                                                                                                        ctx.member.user, event=event)
    except SetupCancel:
        return
    except:
        logger.error(sys.exc_info())
        return
    #
    # END Builder
    # 
    
    
    # Store and Build the public event Event
    try:
        event, eventMsg = await CreateEventDB(ctx, client, config, ctx.get_guild().get_channel(channel[0]), data['color'], data['title'], data['description'], date, 
                                              recuringInterval, recuringUntil, keep_signup_data, data['capacity'], data['thumbImage'], mentions, 
                                              template, option_preset)
    except:
        logger.error(sys.exc_info())
        return

    return event, eventMsg



async def CopyEvent(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, config: Config, event: Events) -> tuple[Events, Message]:
    
    try:
        newEvent, newEventMsg = await CreateEvent(ctx, client, snowflake, config, event=event)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    else:
        if newEvent == None:
            await ctx.edit_response(snowflake , content=Embed(
                description="Copying Event Failed, Try again or Create a [Support Ticket](https://discord.gg/qPTFPQVbMx) if this issue persists."
                ) , flags=MessageFlag.EPHEMERAL | MessageFlag.SUPPRESS_EMBEDS)
            return
        
    ## Google Sheets
    sheets = None
    template = await sync_to_async(newEvent.GetTemplate)()
    if config.is_premium and template:
        try:
            sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name)
        except:
            logger.error(sys.exc_info())
        else:
            try:
                await sheets.CreateSheet(newEvent, newEventMsg.make_link(ctx.guild_id))
            except:
                logger.error(sys.exc_info())
            else:
                newEvent.worksheet_id = sheets.sheet.id
                await newEvent.asave()
    
    ## Create a Google Calendar Event
    if config.calendar_enabled and config.is_premium:     
        try:
            cal: Calendar = Calendar()
        except:
            logger.error(sys.exc_info())
        else:
            if config.calendar_id != None and cal.check_calendar_exists(config.calendar_id):    
                try:
                    await sync_to_async(cal.create_event)(newEvent, config)
                except:
                    logger.error(sys.exc_info())
    ##
    
    # STATS
    try:
        await sync_to_async(Stats_Created.objects.create)(gid=config.id, author=int(ctx.member.id))
    except:
        logger.error(sys.exc_info())
    #
    
    if config.log_channel:
        if config.is_premium:
            await (await config.log(ctx.get_guild())).send(Embed(description=f"{ctx.member.mention} created event [{newEvent.title} @ {newEvent.date_arrow.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({newEventMsg.make_link(ctx.guild_id)})"
                                                f"\nWith [google sheet]({sheets.sheet.url})."))
        else:
            await (await config.log(ctx.get_guild())).send(Embed(description=f"{ctx.member.mention} created event [{newEvent.title} @ {newEvent.date_arrow.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({newEventMsg.make_link(ctx.guild_id)})"))
    
    return newEvent, newEventMsg


def generate_google_calendar_url(title: str, description: str, start_time: arrow.Arrow, end_time: arrow.Arrow = None, location: str = "") -> str:
    """
    Generate a Google Calendar URL for adding an event to the user's calendar.
    
    Args:
        title: Event title
        description: Event description
        start_time: Event start time (arrow.Arrow object)
        end_time: Event end time (arrow.Arrow object, defaults to 1 hour after start)
        location: Event location (optional)
    
    Returns:
        Google Calendar URL string
    """
    import urllib.parse
    
    # Default end time to 1 hour after start if not provided
    if end_time is None:
        end_time = start_time.shift(hours=1)
    
    # Format dates for Google Calendar (YYYYMMDDTHHMMSSZ)
    start_formatted = start_time.to('utc').format('YYYYMMDDTHHmmss') + 'Z'
    end_formatted = end_time.to('utc').format('YYYYMMDDTHHmmss') + 'Z'
    
    # URL encode the parameters
    params = {
        'action': 'TEMPLATE',
        'text': title,
        'dates': f"{start_formatted}/{end_formatted}",
        'details': description,
        'location': location
    }
    
    # Build the URL
    base_url = "https://calendar.google.com/calendar/render"
    query_string = urllib.parse.urlencode(params)
    
    return f"{base_url}?{query_string}"


async def RebuildEventEmbed(rest: RESTClient, event: Events, primaryAttendance: Attendance | Attendance_Linked, 
                            linkedAttendances: list[Attendance_Linked] = None, mainEvtAttendance: Attendance = None) -> list[Embed]:
    config: Config = await sync_to_async(primaryAttendance.Config)()
    guild = await rest.fetch_guild(config.guild)
    author = await rest.fetch_user(event.author) if event.author else None
    
    truncate = config.signup_overflow_method == 0
    
    eventEmbeds: list[Embed] = [Embed(
        title = event.title,
        description = event.description,
        color = Color.of(event.color)
    )]
    
    # Generate Google Calendar URL
    if config.calendar_enabled and not config.is_premium:
        calendar_url = generate_google_calendar_url(event.title, event.description, event.date_arrow)
        calendar_link = f"[Add to Google Calendar]({calendar_url})"
    
    # Create the date field with both Discord timestamp and Google Calendar link
    discord_timestamp = f"<t:{int(event.date_arrow.to('utc').datetime.timestamp())}:F><t:{int(event.date_arrow.to('utc').datetime.timestamp())}:R>"
    
    date_value = f"{discord_timestamp}\n{calendar_link}" if config.calendar_enabled and not config.is_premium else discord_timestamp
    
    if event.recurring_interval > 0:
        # Check if the interval is a multiple of 7 (weeks)
        if event.recurring_interval % 7 == 0:
            weeks = event.recurring_interval // 7
            recurrence_text = f"\n**Recurring**: Every {weeks} week{'s' if weeks > 1 else ''}"
        else:
            recurrence_text = f"\n**Recurring**: Every {event.recurring_interval} day{'s' if event.recurring_interval > 1 else ''}"
        
        if event.recurring_until:
            recurrence_text += f" until <t:{int(arrow.get(event.recurring_until).to('utc').datetime.timestamp())}:D>"
            
        date_value += recurrence_text
    
    eventEmbeds[0].add_field(name='Date', value=date_value, inline=False )
    
    
    try:
        template: Templates = await sync_to_async(event.GetTemplate)()
    except Templates.DoesNotExist:
        eventEmbeds[0].set_footer(text=f"Created by {author.username if author else 'Unknown'}")
    else:
        try:
            if template.name == "Default":
                eventEmbeds[0].set_footer(text=f"Created by {author.username if author else 'Unknown'}", icon=template.thumb)
            else:
                eventEmbeds[0].set_footer(text=f"{template.name} | Created by {author.username if author else 'Unknown'}", icon=template.thumb)
        except:
            logger.error(sys.exc_info())
    
    eventEmbeds[0].timestamp = arrow.utcnow().datetime

    if event.image:
        eventEmbeds[0].set_image(event.image)
    
    option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
    
    current_length = (eventEmbeds[0].total_length() + option_preset.character_count + 10)#+10 for capacity
    splitCount = int((6000 - current_length) / len(option_preset.options))
    if splitCount > 1024:
        splitCount = 1024
        
    
    mainGuild, mainConfig = None, None 
    if type(primaryAttendance) is Attendance_Linked:
        mainConfig: Config = await sync_to_async(mainEvtAttendance.Config)()
        mainGuild = await rest.fetch_guild(mainConfig.guild)
        
        truncate = mainConfig.signup_overflow_method == 0
    
    for i, option in enumerate(option_preset.options):
        signups = primaryAttendance.get_signup_option_list(SignupOption(i))
        confirmed = primaryAttendance.comfirmed
        
        data_ = list()
        
        if signups:
            try:
                d_ = await build_users_split(guild, signups, confirmed=confirmed)
            except:
                logger.error(sys.exc_info())
                continue
            
            data_.append(d_)
        elif truncate:
            data_.append({ "guild": guild.name, "users": [], "user_strings": [] })
        
        if type(primaryAttendance) is Attendance_Linked:
            signups = mainEvtAttendance.get_signup_option_list(SignupOption(i))
            confirmed = mainEvtAttendance.comfirmed
            
            if signups:
                try:
                    d_ = await build_users_split(mainGuild, signups, confirmed=confirmed)
                except:
                    logger.error(sys.exc_info())
                    continue
                
                data_.append(d_)
        
        if linkedAttendances != None:
            for la in linkedAttendances:
                linkedConfig: Config = await sync_to_async(la.Config)()
                linkedGuild: Guild = await rest.fetch_guild(linkedConfig.guild)
                signups = la.get_signup_option_list(SignupOption(i))
                confirmed = la.comfirmed
                
                if signups:
                    try:
                        d_ = await build_users_split(linkedGuild, signups, confirmed=confirmed)
                    except:
                        logger.error(sys.exc_info())
                        continue
                    
                    data_.append(d_)
        
        
        tempString = ''
        currentEmbed = 0
        endString = ''
        try:
            if truncate:
                for x, d in enumerate(data_):
                    if x > 0:
                        endString += f"{d['guild']}: +{len(d['users'])}\n"
        except:
            logger.error(sys.exc_info())
        
        _splitCount = splitCount
        
        for x, d in enumerate(data_):
            if (truncate and x < 1) or not truncate:
                if len(d['user_strings']) > 0:
                    for n, s in enumerate(d['user_strings']):
                        if (len(tempString) + len(s) > splitCount and not truncate) or \
                            (len(tempString) + len(s) + len(endString) + 15 > splitCount and truncate):
                            if truncate:
                                tempString += f"...(+{len(d['users']) - n} more)\n"
                                tempString += endString
                            
                            try:
                                if option_preset.use_capacity == False or option['is_attending'] == False or (event.capacity == None or event.capacity == 0):
                                    eventEmbeds[currentEmbed].add_field(name=option['label'], value=tempString, inline=True )
                                else:
                                    eventEmbeds[currentEmbed].add_field(name=f'{option["label"]}  {len(signups)}/{str(event.capacity)}', value=tempString, inline=True )
                            except:
                                logger.error(sys.exc_info())
                            
                            currentEmbed += 1
                            tempString = ''
                                
                            if truncate:
                                break
                            else:
                                eventEmbeds.append(Embed(color = Color.of(event.color)))
                                splitCount = 1024
                            
                        else:
                            tempString += s
                            
                            if n == len(d['users']) - 1 and truncate:
                                tempString += endString
                                
                                try:
                                    if option_preset.use_capacity == False or option['is_attending'] == False or (event.capacity == None or event.capacity == 0):
                                        eventEmbeds[currentEmbed].add_field(name=option['label'], value=tempString, inline=True )
                                    else:
                                        eventEmbeds[currentEmbed].add_field(name=f'{option["label"]}  {len(signups)}/{str(event.capacity)}', value=tempString, inline=True )
                                except:
                                    logger.error(sys.exc_info())
                else:
                    eventEmbeds[currentEmbed].add_field(name=option['label'], value=f"None\n{endString}", inline=True )
                    
        splitCount = _splitCount
                    
    return eventEmbeds


def BuildEventEmbed(title: str, description: str, capacity: int, thumbImg: str, dateTime: arrow.Arrow, recuringInterval: int,
                    recuringUntil: arrow.Arrow, option_preset: Option_Presets, template: Templates, author: User, calendar_enabled: bool, is_premium: bool, color: str = '#f3df73') -> Embed:
    previewEvent = Embed(
        title = title,
        description = description,
        color = Color.of(color)
    )
    try:
        # Generate Google Calendar URL
        if calendar_enabled and not is_premium:
            calendar_url = generate_google_calendar_url(title, description, dateTime)
            calendar_link = f"[Add to Google Calendar]({calendar_url})"
        
        # Create the date field with both Discord timestamp and Google Calendar link
        discord_timestamp = f"<t:{int(dateTime.to('utc').datetime.timestamp())}:F><t:{int(dateTime.to('utc').datetime.timestamp())}:R>"
        
        date_value = f"{discord_timestamp}\n{calendar_link}" if calendar_enabled and not is_premium else discord_timestamp
        # if recuringInterval > 0:
        #     # Check if the interval is a multiple of 7 (weeks)
        #     if recuringInterval % 7 == 0:
        #         weeks = recuringInterval // 7
        #         recurrence_text = f"\n**Recurring**: Every {weeks} week{'s' if weeks > 1 else ''}"
        #     else:
        #         recurrence_text = f"\n**Recurring**: Every {recuringInterval} day{'s' if recuringInterval > 1 else ''}"
            
        #     if recuringUntil:
        #         recurrence_text += f" until <t:{int(arrow.get(recuringUntil).to('utc').datetime.timestamp())}:D>"
                
        #     date_value += recurrence_text
        previewEvent.add_field(name='Date', value=date_value, inline=False)
    except Exception as e:
        logger.error(e)
    
    for i, option in enumerate(option_preset.options):
        if option_preset.name == "Default" and i == 0:
            if capacity == None:
                previewEvent.add_field(name=option['label'], value='None', inline=True )
            else:
                previewEvent.add_field(name=f'{option["label"]}  0/{str(capacity)}', value='None', inline=True )
        else:
            previewEvent.add_field(name=option['label'], value='None', inline=True )
    
    if not template:
        previewEvent.set_footer(text=f"Created by {author.username}")
    else:
        if template.name == "Default":
            previewEvent.set_footer(text=f"Created by {author.username}")
        else:
            previewEvent.set_footer(text=f"{template.name} | Created by {author.username}", icon=template.thumb)
        
    previewEvent.timestamp = arrow.utcnow().datetime

    if thumbImg:
        previewEvent.set_image(thumbImg)

    
    return previewEvent


async def update_other_events_messages(rest: RESTClient, event: Events, thisGuild: Guild):
    evtConf: Config = await sync_to_async(event.Config)()
    thisConf: Config = await sync_to_async(Config.objects.get)(guild=int(thisGuild.id))
    
    try:
        events: QuerySet = await sync_to_async(Events_Links.objects.filter)(event_id=event)
    except Events_Links.DoesNotExist:
        return
    
    try:
        mainAttendance: Attendance = await sync_to_async(event.GetAttendance)()
        linkedAttendances: list[Attendance_Linked] = []
    except:
        logger.error(sys.exc_info())
        
    try:    
        async for e in events:
            e: Events_Links = e
            linkedAttendances.append(await sync_to_async(e.GetAttendance)())
    except:
        logger.warning(sys.exc_info())
    
    ###
    # Update Main Event Message
    ###
    try:
        if evtConf.id != thisConf.id:
            embeds: list[Embed] = await RebuildEventEmbed(rest, event, mainAttendance, linkedAttendances)
            await rest.edit_message(event.channel, event.message, embeds=embeds, 
                                    components=await BuildComponents(rest, evtConf, await sync_to_async(event.GetOptionPreset)(), event.date_arrow))
    except:
        logger.error(sys.exc_info())
        
    ###
    # Update other links
    ###
    async for e in events:
        e: Events_Links = e
        c: Config = await sync_to_async(e.Config)()
        
        if c.id != thisConf.id:
            otherLinkedAttendances: list[Attendance_Linked] = []
            eAtt = await sync_to_async(e.GetAttendance)()
            
            for x in events:
                x: Events_Links = x
                if x.id != e.id:
                    otherLinkedAttendances.append(await sync_to_async(x.GetAttendance)())

            embeds: list[Embed] = await RebuildEventEmbed(rest, event, eAtt, otherLinkedAttendances, mainAttendance)
            await rest.edit_message(e.channel, e.message, embeds=embeds,
                                    components=await BuildComponents(rest, c, await sync_to_async(event.GetOptionPreset)(), event.date_arrow, linked=True, linkedID=e.id))
            
            ## Edit a Google Calendar Event
            if c.calendar_enabled and c.is_premium:
                try:
                    cal: Calendar = Calendar()
                except:
                    logger.error(sys.exc_info())
                else:
                    if c.calendar_id != None and cal.check_calendar_exists(c.calendar_id):
                        try:
                            await sync_to_async(cal.edit_event)(event, c, linkedEvent=e)
                        except:
                            logger.error(sys.exc_info())
            ##

    
async def update_event_thread(rest: RESTClient, event: Events):
    await rest.edit_channel(event.thread, name=f"{arrow.Arrow.fromdatetime(event.event_date).format('DD-MM-YYYY')} - {event.title}")

async def isUserAnyAttendingSignupOption(user_id: int, attendance: Attendance | Attendance_Linked, event: Events) -> bool:
    preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
    
    for i, option in enumerate(preset.options):
        option: dict = option
        if option['is_attending'] == True:
            if attendance.isSignupOption(SignupOption(i), user_id):
                return True
    return False

#
# Create Event Funcs
#
def GetOptionStyle(color: str) ->  ButtonStyle:
    if color == 'green':
        return ButtonStyle.SUCCESS
    elif color == 'red':
        return ButtonStyle.DANGER
    elif color == 'blurple':
        return ButtonStyle.PRIMARY
    return ButtonStyle.SECONDARY

async def BuildComponents(rest: RESTClient, guildConf: Config, optionPreset: Option_Presets, event_date: arrow.Arrow, linked: bool = False, linkedID: int | None = None):
    now = arrow.utcnow()
    
    #
    # Component Builder
    #
    buttonRow: list[MessageActionRowBuilder] = []
    
    splitoptions = [optionPreset.options[i:i + 5] for i in range(0, len(optionPreset.options), 5)]
    
    
    tentativeDate = guildConf.tentativeDate(event_date)

    x = 0
    for i, s in enumerate(splitoptions, 0):
        buttonRow.append(rest.build_message_action_row())
        
        for p in (s):
            if p['istentative'] == False or tentativeDate > now:
                buttonRow[i].add_interactive_button(GetOptionStyle(p['colour']), buttonNames[x], label=p['label'])
            
            x += 1
        
    if x == 5:
        buttonRow.append(rest.build_message_action_row())
    
    if not linked:
        buttonRow[len(buttonRow)-1].add_interactive_button(ButtonStyle.SECONDARY, 'bastEvSetting', emoji=Emoji.parse('<:settings:1097966215802142832>'))
    else:
        hashids = Hashids(salt=salt)
        buttonRow[len(buttonRow)-1].add_link_button(f"https://{'localhost' if IS_LOCAL else 'baast.app'}/panel/{hashids.encode(int(guildConf.guild))}/event/{linkedID}/linked/", label="Panel")

    return buttonRow



async def BuildEventDB(config: Config, channel: TextableChannel, thread: GuildThreadChannel, message: Message, color: str,
                       title, description, dateTime: arrow.Arrow, recuringInterval: int, recuringUntil: arrow.Arrow, keep_signup_data: bool, capacity, 
                       thumbImg, author: User, option_preset: Option_Presets, template: Templates, 
                       mentions: list[Role], roleset: Preset_Roles = None, recurring = False, eventID: int = None,
                       ) -> Events:
    now = arrow.utcnow()
    
    mentions_ids = [mention.id for mention in mentions]
    
    reminderFlags = []
    for r in config.reminders:
        evdate = dateTime
        evdate = evdate.shift(hours=-r['time'] if r['sequence'] == 'before' else r['time'])
        
        reminderFlags.append(evdate >= now if r['sequence'] == 'before' else evdate <= now)
        
    event: Events = None
    try:
        event, created  = await Events.objects.aupdate_or_create(
            id=int(eventID) if eventID is not None else None,
            gid=config,
            defaults={
                "message": int(message.id),
                "channel": int(channel.id),
                "thread": int(thread.id),
                "author": int(author.id),
                
                "data": {
                    "title": title if title is not None else 'None',
                    "description": description,
                    "capacity": capacity,
                    "thumbImage": thumbImg,
                    "mentions": mentions_ids,
                    "color": color,
                },
                
                "option_preset": option_preset,
                "template": template,
                "roleset": roleset,
                
                "event_date": dateTime.datetime,
                "tz": dateTime.format('ZZZ'),
                "delete_date": None,
                
                "recurring_interval": recuringInterval,
                "recurring_until": recuringUntil.datetime if recuringUntil else None,
                "keep_signup_data": keep_signup_data,
                
                "sentReminders": reminderFlags,
                
                "worksheet_id": None
            }
        )
        
        if created and eventID != None:
            logger.warning(f"Created Event when should have updated an event for ID {eventID} now duped as {event.id}")
            
    except:
        logger.critical(f'{str(sys.exc_info())}')
        if event and eventID == None:
            await event.async_delete()
            
        await thread.delete()
        await message.delete()
        return
    
    return event

async def BuildLinkedEventDB(config: Config, evt: Events, channel: TextableChannel, thread: GuildThreadChannel, message: Message) -> Events_Links:
    now = arrow.utcnow()
    
    reminderFlags = []
    for r in config.reminders:
        evdate = evt.date_arrow
        evdate = evdate.shift(hours=-r['time'] if r['sequence'] == 'before' else r['time'])
        
        reminderFlags.append(evdate >= now if r['sequence'] == 'before' else evdate <= now)

    event: Events_Links | None = None
    try:
        event: Events_Links = await sync_to_async(Events_Links.objects.create)(
            event_id = evt,
            linked_guild = config,
            
            message = message.id,
            channel = channel.id,
            thread = thread.id,
            
            sentReminders = reminderFlags
        )
        
    except:
        logger.critical(f'{sys.exc_info()}')
        if event:
            await event.delete()
        await message.delete()
        return
    
    return event

async def CreateEventDB(ctx: Context | ComponentInteraction, client: Client, config: Config, channel: TextableChannel, color: str, title: str, description: str, 
                      dateTime: arrow.Arrow, recuringInterval: int, recuringUntil: arrow.Arrow, keep_signup_data: bool, capacity: int, thumbImg: str, 
                      mentions: list, template: Templates, option_preset: Option_Presets, roleset: Preset_Roles = None, linked: bool = False, 
                      evntid: int = None) -> tuple[Events, Message]:
    try:
        embed:Embed = BuildEventEmbed(title, description, capacity, thumbImg, dateTime, recuringInterval, recuringUntil, option_preset, template, 
                                      (ctx.user if isinstance(ctx, Context) else ctx.member), bool(config.calendar_enabled), bool(config.is_premium), color=color)
    except:
        logger.error(sys.exc_info())
        raise
    
    try:
        componentRow = await BuildComponents(client.rest, config, option_preset, dateTime)
    except:
        logger.error(sys.exc_info())
        raise

    try:
        mentionStr, everyone = roles_to_string(mentions)
    except:
        logger.error(sys.exc_info())
        raise
    
    try:
        message = await channel.send(content=mentionStr, embed=embed, components=componentRow, role_mentions=mentions, mentions_everyone=everyone)
        thread: GuildPrivateThread = await client.rest.create_message_thread(channel, message, f"{dateTime.format('DD-MM-YYYY')} - {title}", 
                                                                             auto_archive_duration=datetime.timedelta(hours=24*7))
    except:
        logger.error(sys.exc_info())
        raise
    
    if not linked:
        try:
            event = await BuildEventDB(config, channel, thread, message, color, title, description, dateTime, recuringInterval, recuringUntil, keep_signup_data, 
                                       capacity, thumbImg, ctx.user, option_preset, template, mentions, eventID=evntid)
        except:
            logger.error(sys.exc_info())
    else:
        now = arrow.utcnow()
        
        try:
            event: Events = await sync_to_async(Events.objects.get)(id=int(evntid))
            event: Events_Links = await BuildLinkedEventDB(config, event, channel, thread, message)
            
            componentRow = await BuildComponents(client.rest, config, option_preset, dateTime, linked=True, linkedID=event.id)
            await message.edit(components=componentRow)
        except:
            logger.critical(f'{sys.exc_info()}')
            await thread.delete()
            await message.delete()
            return

    return event, message
