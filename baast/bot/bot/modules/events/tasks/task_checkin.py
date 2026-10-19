import sys
import time
import arrow
from asgiref.sync import sync_to_async

from django.db.models import QuerySet

from hikari import ButtonStyle, Embed, GatewayGuild, GuildTextChannel, ForbiddenError, NotFoundError

import lightbulb
from lightbulb import Client

from app.models import Events, Events_Links, Config
from bot.bot.utils.util import ConvertTimeFromDBToValues


from loguru import logger
loader = lightbulb.Loader()


@loader.task(lightbulb.uniformtrigger(minutes=5))
async def event_checkin(client: Client) -> None:
    start = time.process_time()
    
    guild_confs = await sync_to_async(Config.objects.filter)(delete_date=None)
    
    async for config in guild_confs:
        try:
            guild = await client.rest.fetch_guild(config.guild)
        except (NotFoundError, ForbiddenError):
            continue
        except:
            logger.warning(f"{sys.exc_info()}")
            continue
        
        if not config.is_premium:
            continue
        
        reminderTime = ConvertTimeFromDBToValues(config.checkin_t)
        if reminderTime[0] == 0 and reminderTime[1] == 0 and reminderTime[2] == 0: #0:0:0 = Disabled
            continue
        
        await CheckInEvents(client, config, guild)
        
        await CheckInLinkedEvents(client, config, guild)
    
    logger.debug(f'Task \'event_checkin\' took {time.process_time() - start}second(s) to complete')
        
        

async def CheckInEvents(client: Client, config: Config, guild: GatewayGuild):             
    events: QuerySet = await sync_to_async(Events.objects.filter)(gid=config, delete_date=None) #list[Events]

    if not await sync_to_async(events.exists)():
        return
    
    events: list[Events] = await sync_to_async(list)(events)
    
    for event in events:
        event: Events = event
        
        if not event.sentCheckin:
            
            checkInTime = ConvertTimeFromDBToValues(config.checkin_t)
            checkInTimeDate = arrow.get(event.event_date).to('utc').shift(hours=-checkInTime[0], minutes=-checkInTime[1], seconds=-checkInTime[2])
            now = arrow.utcnow()

            if event.id == 128 or (checkInTimeDate <= now and arrow.get(event.event_date).to('utc') > now):
                # message: Message = None
                try:
                    thread: GuildTextChannel = await client.rest.fetch_channel(event.thread)
                except:
                    logger.debug(f'Event {event.id} in guild {guild.id} has no thread')
                    event.sentCheckin = True
                    await event.asave()
                    pass
                else:
                    event.sentCheckin = True
                    await event.asave()
                    
                    buttons = (client.rest.build_message_action_row()
                            .add_interactive_button(ButtonStyle.SUCCESS, 'baastConfirm', label='Confirm')
                            .add_interactive_button(ButtonStyle.DANGER, 'baastDecline', label='Decline'))
                    
                    try:
                        checkinMessage = await thread.send(embed=Embed(title=f'Event Confirmation', 
                                                    description=f'Please confirm with the buttons below if your stil attending this event or not.',
                                                    colour=0x3ba55c),
                                        component=buttons)
                        
                        await client.rest.pin_message(thread, checkinMessage)
                    except:
                        logger.error(sys.exc_info())
                        continue
                
async def CheckInLinkedEvents(client: Client, config: Config, guild: GatewayGuild):             
    events: QuerySet = await sync_to_async(Events_Links.objects.filter)(linked_guild=config)

    if not await sync_to_async(events.exists)():
        return
    
    events: list[Events_Links] = await sync_to_async(list)(events)
    
    for event in events:
        event: Events_Links = event
        e: Events = await sync_to_async(event.Event)()
        
        if not event.sentCheckin:
            
            checkInTime = ConvertTimeFromDBToValues(config.checkin_t)
            checkInTimeDate = arrow.get(e.event_date).to('utc').shift(hours=-checkInTime[0], minutes=-checkInTime[1], seconds=-checkInTime[2])
            now = arrow.utcnow()

            if e.id == 128 or (checkInTimeDate <= now and arrow.get(e.event_date).to('utc') > now):
                thread: GuildTextChannel = await client.rest.fetch_channel(event.thread)
                
                event.sentCheckin = True
                await sync_to_async(event.save)()
                
                
                buttons = (client.rest.build_message_action_row()
                        .add_interactive_button(ButtonStyle.SUCCESS, 'baastConfirm', label='Confirm')
                        .add_interactive_button(ButtonStyle.DANGER, 'baastDecline', label='Decline'))
                
                try:
                    checkinMessage = await thread.send(embed=Embed(title=f'Event Confirmation', 
                                                description=f'Please confirm with the buttons below if your stil attending this event or not.',
                                                colour=0x3ba55c),
                                    component=buttons)
                    
                    await client.rest.pin_message(thread, checkinMessage)
                except:
                    logger.error(sys.exc_info())
                    continue
