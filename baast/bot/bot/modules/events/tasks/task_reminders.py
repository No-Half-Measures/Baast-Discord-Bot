import sys, time
import arrow
from asgiref.sync import sync_to_async

from hikari import Embed, GatewayGuild, Color, GuildTextChannel, ForbiddenError, Permissions, NotFoundError
import lightbulb
from lightbulb import Client

from app.models import Events, Events_Links, Config, Option_Presets, Attendance, Attendance_Linked, SignupOption
from discord.models import User
from bot.bot.utils.util import HasChannelPermission
from cache.helpers import _safe_get_cache_view

from loguru import logger


loader = lightbulb.Loader()

def GetUser(users, index):
    return users[index]

@loader.task(lightbulb.uniformtrigger(minutes=5))
async def reminders_task(client: Client) -> None:
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
        
        await SendReminders(client, config, guild)
        await SendLinkedReminders(client, config, guild)

    logger.debug(f'Task \'reminders_task\' took {time.process_time() - start}second(s) to complete')

async def SendReminders(client: Client, config: Config, guild: GatewayGuild):
    try:
        events: list[Events] = await sync_to_async(list)(Events.objects.filter(gid=config, delete_date=None))
    except Events.DoesNotExist:
        return
    
    now = arrow.utcnow()
    # Dictionary to track messages per user
    user_reminders = {}
    log_embeds = []
    
    for i, reminder_config in enumerate(config.reminders):
        for event in events:
            try:
                event.sentReminders[i]
            except IndexError:
                event.sentReminders.append(False)
                await event.asave()
            
            if not event.sentReminders[i]:  # Check if this reminder was already sent
                reminder_time = arrow.get(event.event_date).shift(hours=-int(reminder_config['time']))
                
                if reminder_time <= now and arrow.get(event.event_date) > now:
                    try:
                        message = await client.rest.fetch_message(event.channel, event.message)
                    except:
                        logger.warning(f'Message not found for event {event.id} and is not marked for deletion!')
                        
                        event.delete_date = arrow.utcnow().shift(days=7).datetime
                        await event.asave()
                        
                        continue
                    
                    if not message:
                        logger.warning(f'Unable to get message for event {event.id}')
                        continue
                    
                    attendance: Attendance = await sync_to_async(event.GetAttendance)()
                    option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
                    
                    # Get list of users to notify based on reminder target
                    members_to_notify = []
                    
                    if reminder_config['target'] == 'all':
                        channel = guild.get_channel(event.channel)
                        if channel:
                            members_list = _safe_get_cache_view(guild.get_members, f"guild {guild.id} members")
                            for member in members_list:
                                if HasChannelPermission(channel, guild, member):
                                    members_to_notify.append(member.id)
                    
                    elif reminder_config['target'] == 'nosign':
                        signed_up_members = attendance.get_all_responses()
                        channel = guild.get_channel(event.channel)
                        if channel:
                            members_list = _safe_get_cache_view(guild.get_members, f"guild {guild.id} members")
                            for member in members_list:
                                has_permission = HasChannelPermission(channel, guild, member)
                                
                                if has_permission and member.id not in signed_up_members and not member.is_bot:
                                    members_to_notify.append(member.id)
                    
                    else:
                        for opt_index, option in enumerate(option_preset.options):
                            if (reminder_config['target'] == 'tentative' and option['istentative']) or \
                               (reminder_config['target'] == 'attending' and option['is_attending']) or \
                               (reminder_config['target'] == 'confirmed' and option['is_attending']):
                                
                                if option['send_notifcations']:
                                    signups = attendance.get_signup_option_list(SignupOption(opt_index))
                                    for member_id in signups:
                                        if reminder_config['target'] != 'confirmed' or attendance.isConfirmed(member_id):
                                            members_to_notify.append(member_id)
                    
                    # Get user objects for notification preferences
                    user_ids = list(set(members_to_notify))  # Remove duplicates
                    users: list[User] = await sync_to_async(User.objects.filter, thread_sensitive=True)(id__in=user_ids)
                    user_ids_list: list[int] = await sync_to_async(list)(await sync_to_async(users.values_list)('id', flat=True))
                    
                    mentions = ''
                    for member_id in user_ids:
                        member = guild.get_member(member_id)
                        if member and not member.is_bot:
                            if int(member.id) in user_ids_list:
                                user_index = user_ids_list.index(int(member.id))
                                user = await sync_to_async(GetUser)(users, user_index)
                                
                                if user.notifications_enabled:
                                    # Add event to user's bundle of reminders
                                    if member.id not in user_reminders:
                                        user_reminders[member.id] = []
                                    
                                    event_info = {
                                        'message': FormatReminderMessage(reminder_config, guild, event, message.make_link(guild)),
                                        'color': reminder_config['color']
                                    }
                                    user_reminders[member.id].append(event_info)
                                    mentions += f'{member.mention} '
                    
                    # Create log embed for this event
                    if mentions:
                        log_embeds.append(Embed(
                            description=f"Sending {reminder_config['time']}hr reminder for [{event.title}]({message.make_link(guild)}) "
                                     f"<t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:R> "
                                     f"to {reminder_config['target']} users.\n**To:** {mentions}"
                        ))
                    
                    # Mark reminder as sent
                    event.sentReminders[i] = True
                    await sync_to_async(event.save)()
    
    # Send bundled reminders to users
    for member_id, events_info in user_reminders.items():
        member = guild.get_member(member_id)
        if member:
            embeds = []
            for event in events_info:
                reminder: Embed = Embed(
                    description=event['message'],
                    color=Color.of(event['color'])
                )
                
                reminder.set_footer(text='Disable reminders with /reminders off')
                embeds.append(reminder)
            
            try:
                await member.send(embeds=embeds)
            except ForbiddenError:
                logger.warning(f'Unable to send bundled reminder to user {member_id}:{member.username}')
    
    # Send logs
    if config.log_channel and log_embeds:
        log_channel: GuildTextChannel = guild.get_channel(config.log_channel)
        if HasChannelPermission(log_channel, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
            for i in range(0, len(log_embeds), 10):  # Send in batches of 10 to avoid Discord limits
                await log_channel.send(embeds=log_embeds[i:i+10])

async def SendLinkedReminders(client: Client, config: Config, guild: GatewayGuild):
    try:
        linked_events: list[Events_Links] = await sync_to_async(list)(Events_Links.objects.filter(linked_guild=config))
    except Events_Links.DoesNotExist:
        return
    
    now = arrow.utcnow()
    # Dictionary to track messages per user
    user_reminders = {}
    log_embeds = []
    
    for i, reminder_config in enumerate(config.reminders):
        for link in linked_events:
            try:
                link.sentReminders[i]
            except IndexError:
                link.sentReminders.append(False)
                await event.asave()
            
            event: Events = await sync_to_async(link.Event)()
            
            if not link.sentReminders[i]:  # Check if this reminder was already sent
                reminder_time = arrow.get(event.event_date).shift(hours=-int(reminder_config['time']))
                
                if reminder_time <= now and arrow.get(event.event_date) > now:
                    try:
                        message = await client.rest.fetch_message(link.channel, link.message)
                    except:
                        logger.warning(f'Message not found for linked event {link.id} and is not marked for deletion!')
                        continue
                    
                    if not message:
                        logger.warning(f'Unable to get message for linked event {link.id}')
                        continue
                    
                    attendance: Attendance_Linked = await sync_to_async(link.GetAttendance)()
                    option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
                    
                    # Get list of users to notify based on reminder target
                    members_to_notify = []
                    
                    if reminder_config['target'] == 'all':
                        for member_id in await sync_to_async(attendance.get_all_responses)():
                            members_to_notify.append(member_id)
                    
                    elif reminder_config['target'] == 'nosign':
                        # Get all members who haven't signed up yet
                        signed_up_members = attendance.get_all_responses()
                        channel = guild.get_channel(event.channel)
                        if channel:
                            members_list = _safe_get_cache_view(guild.get_members, f"guild {guild.id} members")
                            for member in members_list:
                                # Check if member has view permission and hasn't signed up
                                has_permission = HasChannelPermission(channel, guild, member)
                                
                                if has_permission and member.id not in signed_up_members and not member.is_bot:
                                    members_to_notify.append(member.id)
                    
                    else:
                        for opt_index, option in enumerate(option_preset.options):
                            if (reminder_config['target'] == 'tentative' and option['istentative']) or \
                               (reminder_config['target'] == 'attending' and option['is_attending']) or \
                               (reminder_config['target'] == 'confirmed' and option['is_attending']):
                                
                                if option['send_notifcations']:
                                    signups = attendance.get_signup_option_list(SignupOption(opt_index))
                                    for member_id in signups:
                                        if reminder_config['target'] != 'confirmed' or attendance.isConfirmed(member_id):
                                            members_to_notify.append(member_id)
                    
                    # Get user objects for notification preferences
                    user_ids = list(set(members_to_notify))  # Remove duplicates
                    users: list[User] = await sync_to_async(User.objects.filter, thread_sensitive=True)(id__in=user_ids)
                    user_ids_list: list[int] = await sync_to_async(list)(await sync_to_async(users.values_list)('id', flat=True))
                    
                    mentions = ''
                    for member_id in user_ids:
                        member = guild.get_member(member_id)
                        if member and not member.is_bot:
                            if int(member.id) in user_ids_list:
                                user_index = user_ids_list.index(int(member.id))
                                user = await sync_to_async(GetUser)(users, user_index)
                                
                                if user.notifications_enabled:
                                    # Add event to user's bundle of reminders
                                    if member.id not in user_reminders:
                                        user_reminders[member.id] = []
                                    
                                    event_info = {
                                        'message': FormatReminderMessage(reminder_config, guild, event, message.make_link(guild)),
                                        'color': reminder_config['color']
                                    }
                                    user_reminders[member.id].append(event_info)
                                    mentions += f'{member.mention} '
                    
                    # Create log embed for this event
                    if mentions:
                        log_embeds.append(Embed(
                            description=f"Sending {reminder_config['time']}hr reminder for linked event [{event.title}]({message.make_link(guild)}) "
                                     f"<t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:R> "
                                     f"to {reminder_config['target']} users.\n**To:** {mentions}"
                        ))
                    
                    # Mark reminder as sent
                    link.sentReminders[i] = True
                    await sync_to_async(link.save)()
    
    # Send bundled reminders to users
    for member_id, events_info in user_reminders.items():
        member = guild.get_member(member_id)
        if member:
            embeds = []
            for event in events_info:
                reminder: Embed = Embed(
                    description=event['message'],
                    color=Color.of(event['color'])
                )
                
                reminder.set_footer(text='Disable reminders with /reminders off')
                embeds.append(reminder)
            
            try:
                await member.send(embeds=embeds)
            except ForbiddenError:
                logger.warning(f'Unable to send bundled reminder to user {member_id}:{member.username}')
    
    # Send logs
    if config.log_channel and log_embeds:
        log_channel: GuildTextChannel = guild.get_channel(config.log_channel)
        if HasChannelPermission(log_channel, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
            for i in range(0, len(log_embeds), 10):  # Send in batches of 10 to avoid Discord limits
                await log_channel.send(embeds=log_embeds[i:i+10])

def FormatReminderMessage(reminder_config: dict, guild: GatewayGuild, event: Events, discord_url: str = None):
    """
    Format a reminder message template by replacing placeholders with actual event values.
    
    Args:
        reminder_config: Dictionary containing the reminder configuration with message template
        event: The event object containing event details
        discord_url: URL to the Discord message (optional)
    
    Returns:
        Formatted reminder message string
    """
    # Get the message template from the reminder configuration
    template = reminder_config.get('message', "")
    
    if not template:
        # If no template is provided, return empty string
        return ""
    
    # Get timestamp for Discord formatting
    timestamp = int(arrow.get(event.event_date).to("utc").datetime.timestamp())
    
    # Create dictionary of all possible placeholder values
    format_dict = {
        'title': event.title,
        'description': event.description,
        'discord_url': discord_url or '',
        'sheet_url': '',
        'datetime_long': f"<t:{timestamp}:F>",  # Discord format for full date/time
        'datetime_short': f"<t:{timestamp}:f>",  # Discord format for short date/time
        'datetime_relative': f"<t:{timestamp}:R>",  # Discord format for relative time
        'date': f"<t:{timestamp}:D>",  # Discord format for date only
        'time': f"<t:{timestamp}:t>",  # Discord format for time only
        'epoch': timestamp,
        'channel': guild.get_channel(event.channel).mention
    }
    
    # Try to format the template with the values
    try:
        return template.format(**format_dict)
    except KeyError as e:
        # Log unknown placeholders but return best effort formatting
        logger.warning(f"Unknown placeholder in reminder template: {e}")
        return template