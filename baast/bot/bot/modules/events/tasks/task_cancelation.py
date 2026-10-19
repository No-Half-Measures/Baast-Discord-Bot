import asyncio
import time
import sys
import arrow
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from asgiref.sync import sync_to_async
from django.db.models import Prefetch

import hikari
from hikari import Embed, GatewayGuild, MessageFlag, ForbiddenError, NotFoundError

import lightbulb
from lightbulb import Client

from app.models import Events, Config, Attendance, Option_Presets
from bot.bot.utils.enums import SignupOption
from discord.models import User
from django.db import models

from loguru import logger

loader = lightbulb.Loader()


@loader.task(lightbulb.uniformtrigger(minutes=10))
async def event_cancel(client: Client) -> None:
    """Main task to process event cancellations across all guilds."""
    start = time.process_time()
    
    try:
        # Fetch all configs with their events in a single query
        guild_confs: List[Config] = await sync_to_async(list)(
            Config.objects.filter(delete_date=None)  # type: ignore
            .prefetch_related(
                Prefetch(
                    'events_set',
                    queryset=Events.objects.filter(  # type: ignore
                        delete_date__isnull=False,
                        sentCancelationMsg=False
                    ).select_related('option_preset')
                )
            )
        )
        
        if not guild_confs:
            logger.debug("No guilds with events to process")
            return
        
        # Process guilds in batches to avoid overwhelming Discord API
        batch_size = 10
        for i in range(0, len(guild_confs), batch_size):
            batch = guild_confs[i:i + batch_size]
            await _process_guild_batch(client, batch)
            
    except Exception as e:
        logger.error(f"Critical error in event_cancel task: {e}")
    finally:
        logger.debug(f'Task \'event_cancel_message\' took {time.process_time() - start:.2f} second(s) to complete')


async def _process_guild_batch(client: Client, guild_configs: List[Config]) -> None:
    """Process a batch of guild configurations."""
    guild_tasks = []
    
    for config in guild_configs:
        # Only process configs that have events to cancel
        events_count = await sync_to_async(lambda: config.events_set.count())()  # type: ignore
        if events_count > 0:
            guild_tasks.append(_process_guild_events(client, config))
    
    if guild_tasks:
        # Process guilds concurrently but limit concurrency
        await asyncio.gather(*guild_tasks, return_exceptions=True)


async def _process_guild_events(client: Client, config: Config) -> None:
    """Process events for a single guild."""
    try:
        guild = await client.rest.fetch_guild(int(config.guild))  # type: ignore
    except (NotFoundError, ForbiddenError) as e:
        logger.warning(f"Guild {config.guild} not accessible: {e}")
        return
    except Exception as e:
        logger.error(f"Unexpected error fetching guild {config.guild}: {e}")
        return
    
    try:
        await _check_and_process_events(client, config, guild)
    except Exception as e:
        logger.error(f'Error processing events for Guild {guild.name}: {e}')
        

async def _check_and_process_events(client: Client, config: Config, guild) -> None:
    """Check and process events that need cancellation notifications."""
    now = arrow.utcnow()
    
    # Get events that need processing (already prefetched)
    all_events = await sync_to_async(list)(config.events_set.all())  # type: ignore
    events_to_process = [
        event for event in all_events
        if event.delete_date is not None and not event.sentCancelationMsg
    ]
    
    if not events_to_process:
        return
    
    # Process events concurrently
    event_tasks = []
    for event in events_to_process:
        dDate = arrow.get(event.delete_date)
        cancelDate = dDate.shift(hours=-((24*7)-1))
        
        if cancelDate.datetime < now:
            event_tasks.append(_process_event_cancellation(client, event, guild))
    
    if event_tasks:
        await asyncio.gather(*event_tasks, return_exceptions=True)


async def _process_event_cancellation(client: Client, event: Events, guild: GatewayGuild) -> None:
    """Process cancellation for a single event."""
    try:
        # Create announcement embed
        announcement = Embed(
            title='Event Canceled',
            description=f'The event "{event.title}" on the {event.date_discord} in {event.date_discord_relative} has been Canceled.',
            color=hikari.Color(0xFF7900)
        )
        
        # Get option preset and attendance
        option_preset = await sync_to_async(event.GetOptionPreset)()
        if not option_preset:
            logger.warning(f'No option preset for event {event.id}')
            return
            
        attendance = await sync_to_async(event.GetAttendance)()
        if not attendance:
            logger.warning(f'No attendance record for event {event.id}')
            return
        
        # Collect all user IDs that need notifications
        user_ids_to_notify = set()
        attending_options = []
        
        for i, option in enumerate(option_preset.options):
            if option.get('is_attending', False) or option.get('istentative', False):
                attending_options.append(option['label'])
                
                signup_count = await sync_to_async(attendance.get_signup_option_count)(SignupOption(i))
                if signup_count > 0:
                    signups = attendance.get_signup_option_list(SignupOption(i))
                    user_ids_to_notify.update(signups)
        
        if not user_ids_to_notify:
            logger.debug(f'No users to notify for event {event.id}')
            await _mark_event_as_processed(event)
            return
        
        # Fetch user data in batch
        users_data = await _fetch_users_batch(list(user_ids_to_notify))
        
        # Send notifications
        mentions = await _send_notifications(
            client, guild, users_data, user_ids_to_notify, announcement
        )
        
        # Log the cancellation
        logger.info(
            f"Sent event cancellation notification for '{event.title}' "
            f"to {len(mentions)} users set as {', '.join(attending_options)}"
        )
        
        # Mark event as processed
        await _mark_event_as_processed(event)
        
    except Exception as e:
        logger.error(f'Error processing cancellation for event {event.id}: {e}')


async def _fetch_users_batch(user_ids: List[int]) -> Dict[int, User]:
    """Fetch user data in a single batch query."""
    try:
        users = await sync_to_async(list)(
            User.objects.filter(id__in=user_ids, notifications_enabled=True)
            .only('id', 'notifications_enabled')
        )
        return {user.id: user for user in users}
    except Exception as e:
        logger.error(f'Error fetching users batch: {e}')
        return {}


async def _send_notifications(
    client: Client, 
    guild: GatewayGuild, 
    users_data: Dict[int, User], 
    user_ids: set, 
    announcement: Embed
) -> List[str]:
    """Send notifications to users and return list of mentions."""
    mentions = []
    
    # Process notifications in batches to avoid rate limits
    batch_size = 5
    user_id_list = list(user_ids)
    
    for i in range(0, len(user_id_list), batch_size):
        batch = user_id_list[i:i + batch_size]
        batch_tasks = []
        
        for user_id in batch:
            if user_id in users_data:
                batch_tasks.append(_send_single_notification(guild, user_id, announcement))
        
        if batch_tasks:
            batch_mentions = await asyncio.gather(*batch_tasks, return_exceptions=True)
            mentions.extend([m for m in batch_mentions if m and not isinstance(m, Exception)])
    
    return mentions


async def _send_single_notification(guild: GatewayGuild, user_id: int, announcement: Embed) -> Optional[str]:
    """Send notification to a single user."""
    try:
        member = guild.get_member(user_id)
        if member and not member.is_bot:
            await member.send(embed=announcement, flags=MessageFlag.EPHEMERAL)
            return member.mention
    except hikari.ForbiddenError:
        logger.warning(f'Cannot send DM to user {user_id}')
    except Exception as e:
        logger.warning(f'Error sending notification to user {user_id}: {e}')
    
    return None


async def _mark_event_as_processed(event: Events) -> None:
    """Mark event as having sent cancellation message."""
    try:
        event.sentCancelationMsg = True
        await sync_to_async(event.save)()
    except Exception as e:
        logger.error(f'Error marking event {event.id} as processed: {e}')


# Legacy function - kept for compatibility but not used in optimized version
def GetUser(users, index):
    """Legacy function for getting user by index."""
    return users[index]
