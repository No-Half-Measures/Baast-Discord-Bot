import sys
import arrow
import time
import datetime
from asgiref.sync import sync_to_async

from django.db.models import QuerySet

from hikari import Embed, GuildPrivateThread, Message, NotFoundError, GuildTextChannel, RESTGuild, ForbiddenError

import lightbulb
from lightbulb import Client

from app.models import Events, Config, Events_Links
from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.event_utils import BuildComponents, RebuildEventEmbed, roles_to_string, update_other_events_messages
from bot.bot.utils.util import ConvertTimeFromDBToValues


from loguru import logger
loader = lightbulb.Loader()


@loader.task(lightbulb.uniformtrigger(minutes=10))
async def event_expired(client: Client) -> None:
    start = time.process_time()
    
    guild_confs = await sync_to_async(Config.objects.filter)(delete_date=None)
    
    async for config in guild_confs:
        if not config:
            continue
        
        try:
            guild = await client.rest.fetch_guild(config.guild)
        except (NotFoundError, ForbiddenError):
            continue
        except Exception as e:
            logger.error(f"{e}")
            continue

        events: QuerySet = await sync_to_async(Events.objects.filter)(gid=config, delete_date=None) #list[Events]

        if not await sync_to_async(events.exists)():
            continue
        
        events: list[Events] = await sync_to_async(list)(events)
        
        for event in events:
            if not event.isMarkedDelete:
                cleanTime = ConvertTimeFromDBToValues(config.autoclean_t)
                cleanTimeDate = arrow.get(event.event_date).to('utc').shift(hours=+cleanTime[0], minutes=+cleanTime[1], seconds=+cleanTime[2])
                now = arrow.utcnow()
                
                if cleanTimeDate <= now:
                    # Check if this is a recurring event
                    if (event.recurring_interval > 0):
                        await handle_event_recurring(client, config, event, guild)
                    else:
                        # Non-recurring event, handle deletion
                        await handle_event_deletion(client, config, event, guild)
                elif event.event_date < now:
                    await disable_event_buttons(client, config, event, guild)
    
    logger.debug(f'Task \'event_expired\' took {time.process_time() - start}second(s) to complete')

async def handle_event_deletion(client: Client, config: Config, event: Events, guild: RESTGuild):
    """Handle the deletion of an event."""
    message: Message = None
    
    try:
        message = await client.rest.fetch_message(event.channel, event.message)
    except NotFoundError:
        message = None
    except:
        logger.error(sys.exc_info())
        return
    else:
        if message:
            try:
                await message.delete()
            except:
                logger.warning(sys.exc_info())
    
    try:
        if config.thread_delete_method == 1:
            await client.rest.edit_channel(event.thread, archived=True)
        else:
            await client.rest.delete_channel(event.thread)
    except:
        pass
    
    if config.is_premium and event.worksheet_id != None:
        try:
            sheets = Sheet(config, guild.name, event)
        except:
            logger.error(sys.exc_info())
        else:
            try:
                await sheets.ArchiveSheet()
            except:
                logger.error(sys.exc_info())
    
    try:
        await event.async_delete()
    except:
        logger.warning(f'Failed to deleted event data {config.guild}, {event.channel}, {event.message}... \n {sys.exc_info()}')
    
    if message and config.logs_enabled:
        logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
        if logChnl:
            await logChnl.send(embed=Embed(description=f"Event Expired - {event.title} @ <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:R>"))

async def disable_event_buttons(client: Client, config: Config, event: Events, guild: RESTGuild):
    """Disable the event buttons."""
    message: Message = None
    try:
        message = await client.rest.fetch_message(event.channel, event.message)
    except NotFoundError:
        message = None
        logger.warning(f'Message not found for event [{event.id}] {event.title} in channel {event.channel} for guild {guild.id}')
        return
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await client.rest.edit_message(event.channel, event.message, message.content, components=None)
    except:
        logger.warning(sys.exc_info())

async def handle_event_recurring(client: Client, config: Config, event: Events, guild: RESTGuild):
    """Handle the deletion of an event."""
    # Calculate the next event date
    now = arrow.utcnow().datetime
    next_date = arrow.get(event.event_date).shift(days=+event.recurring_interval)
    
    while next_date.datetime < now:
        next_date = next_date.shift(days=+event.recurring_interval)
        if (event.recurring_until != None and event.recurring_until < next_date.datetime):
            break
    
    # Check if we've reached the recurring_until date
    if event.recurring_until != None and event.recurring_until < next_date.datetime:
        # The recurring event has ended, delete it
        await handle_event_deletion(client, config, event, guild)
    else:
        # Delete the old message
        old_message = None
        try:
            old_message = await client.rest.fetch_message(event.channel, event.message)
        except NotFoundError:
            pass
        except:
            logger.error(sys.exc_info())
        
        # Update the event date to the next occurrence
        event.event_date = next_date.datetime
        
        # Reset reminder flags
        event.sentReminders = [False] * len(config.reminders)
        event.sentCheckin = False
        
        attendance = await sync_to_async(event.GetAttendance)()
        # Reset attendance data if needed
        if not event.keep_signup_data:
            await sync_to_async(attendance.reset_attendance)()
        else:
            await sync_to_async(attendance.reset_confirmed)()
        
        # Create a new event message
        try:
            option_preset = await sync_to_async(event.GetOptionPreset)()
            
            embeds = await RebuildEventEmbed(client.rest, event, attendance)
            channel: GuildTextChannel = await client.rest.fetch_channel(event.channel)
            componentRow = await BuildComponents(client.rest, config, option_preset, event.date_arrow)
            
            mentions_roles = None
            try:
                mentions_roles = [guild.get_role(role_id) for role_id in event.mentions]
            except KeyError:
                pass
            except:
                logger.error(sys.exc_info())
                return
            
            mentionStr = None
            everyone = False
            if mentions_roles:
                try:
                    mentionStr, everyone = roles_to_string(mentions_roles)
                except:
                    logger.error(sys.exc_info())
                    raise
            
            
            new_message = await channel.send(content=mentionStr, embeds=embeds, components=componentRow, role_mentions=mentions_roles, mentions_everyone=everyone)
            
            try:
                if config.thread_delete_method == 1:
                    await client.rest.edit_channel(event.thread, archived=True)
                else:
                    await client.rest.delete_channel(event.thread)
            except:
                logger.warning(sys.exc_info())
                
            thread: GuildPrivateThread = await client.rest.create_message_thread(channel, new_message, f"{event.date_arrow.format('DD-MM-YYYY')} - {event.title}", 
                                                                             auto_archive_duration=datetime.timedelta(hours=24*7))
            
            # Update the event with the new message ID
            event.message = new_message.id
            event.thread = thread.id
            
            await event.asave()
        except:
            logger.error(f"Failed to repost event message for {event.title}: {sys.exc_info()}")
            return
            
        ## Sheets
        template = await sync_to_async(event.GetTemplate)()
        if config.is_premium and template != None:
            try:
                sheets = Sheet(config, guild.name, event)
            except:
                logger.error(f'Error Building Sheet Obj:\n {sys._getframe()}:{sys.exc_info()}')
            #
            try:
                await sheets.ArchiveSheet()
            except:
                logger.error(f'Error Archiving Worksheet:\n {sys._getframe()}:{sys.exc_info()}')
            #
            try:
                await sheets.CreateSheet(event, new_message.make_link(guild))
            except:
                logger.error(f'Error Creating Worksheet:\n {sys._getframe()}:{sys.exc_info()}')
            
        # Save the updated event
        if old_message:
            await old_message.delete()
        
        await handle_linked_event_recurring(client, event, guild)
        
        # Log the event recurrence
        if config.logs_enabled:
            logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
            if logChnl:
                await logChnl.send(embed=Embed(description=f"Event Recurring - [{event.title}]({new_message.make_link(guild)}) next @ <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"))
                

async def handle_linked_event_recurring(client: Client, event: Events, guild: RESTGuild):
    """Handle the deletion of a linked event."""
    
    linked_events = await sync_to_async(list)(Events_Links.objects.filter(event_id=event))

    for linked_event in linked_events:
        config: Config = await sync_to_async(linked_event.Config)()
        
        linked_event: Events_Links = linked_event
        linked_event_attendance = await sync_to_async(linked_event.GetAttendance)()
        
        mainAttendance = await sync_to_async(event.GetAttendance)()
        
        if not event.keep_signup_data:
            await sync_to_async(linked_event_attendance.reset_attendance)()
        else:
            await sync_to_async(linked_event_attendance.reset_confirmed)()
            
        old_message = None
        try:
            old_message = await client.rest.fetch_message(linked_event.channel, linked_event.message)
        except NotFoundError:
            pass
        except:
            logger.error(sys.exc_info())
            
        
        try:
            option_preset = await sync_to_async(event.GetOptionPreset)()
            
            embeds = await RebuildEventEmbed(client.rest, event, linked_event_attendance, mainEvtAttendance=mainAttendance)
            
            channel: GuildTextChannel = await client.rest.fetch_channel(linked_event.channel)
            componentRow = await BuildComponents(client.rest, config, option_preset, event.date_arrow, linked=True, linkedID=linked_event.id)
            new_message = await channel.send(content=old_message.content, embeds=embeds, components=componentRow, role_mentions=old_message.role_mention_ids, mentions_everyone=old_message.mentions_everyone)
            
            
            try:
                if config.thread_delete_method == 1:
                    await client.rest.edit_channel(linked_event.thread, archived=True)
                else:
                    await client.rest.delete_channel(linked_event.thread)
            except:
                logger.warning(sys.exc_info())
                
            thread: GuildPrivateThread = await client.rest.create_message_thread(channel, new_message, f"{event.date_arrow.format('DD-MM-YYYY')} - {event.title}", 
                                                                                auto_archive_duration=datetime.timedelta(hours=24*7))
            
            
            # Update the event with the new message ID
            linked_event.message = new_message.id
            linked_event.thread = thread.id
            
            await linked_event.asave()
        except:
            logger.error(f"Failed to repost event message for {await sync_to_async(linked_event.title)}: {sys.exc_info()}")
            
            
        if old_message:
            try:
                await old_message.delete()
            except:
                logger.warning(sys.exc_info())
                
        # Log the event recurrence
        if config.logs_enabled:
            logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
            if logChnl:
                await logChnl.send(embed=Embed(description=f"Linked Event Recurring - [{event.title}]({new_message.make_link(guild)}) next @ <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"))
