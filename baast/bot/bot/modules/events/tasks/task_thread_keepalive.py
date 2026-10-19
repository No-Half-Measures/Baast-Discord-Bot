import sys
from asgiref.sync import sync_to_async

from hikari import ForbiddenError, NotFoundError
import lightbulb
from lightbulb import Client

from app.models import Events, Events_Links, Config


from loguru import logger
loader = lightbulb.Loader()


@loader.task(lightbulb.uniformtrigger(minutes=10))
async def event_cancel_message(client: Client) -> None:
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
        
        await handelEventsTreads(config, client.rest)
        await handelLinkedEventsTreads(config, client.rest)

async def handelEventsTreads(config: Config, rest):
    try:
        events = await sync_to_async(Events.objects.filter)(gid=config, delete_date=None)
    except Events.DoesNotExist:
        return
    
    async for event in events:
        try:
            threads = await rest.fetch_public_archived_threads(event.channel)
        except (NotFoundError, ForbiddenError):
            continue
        except:
            logger.warning(f"{sys.exc_info()}")
            continue
        else:
            for thread in threads:
                if thread.id == event.thread:
                    if thread.is_archived:
                        await rest.edit_channel(thread.id, archived=False)

async def handelLinkedEventsTreads(config: Config, rest):
    try:
        events: list[Events_Links] = await sync_to_async(Events_Links.objects.filter)(linked_guild=config)
    except Events.DoesNotExist:
        return
    
    async for event in events:
        try:
            threads = await rest.fetch_public_archived_threads(event.channel)
        except (NotFoundError, ForbiddenError):
            continue
        except:
            logger.warning(f"{sys.exc_info()}")
            continue
        else:
            for thread in threads:
                if thread.id == event.thread:
                    if thread.is_archived:
                        await rest.edit_channel(thread.id, archived=False)
