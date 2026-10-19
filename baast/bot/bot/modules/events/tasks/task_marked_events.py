import sys, time
import arrow
from asgiref.sync import sync_to_async

from django.db.models import QuerySet

from hikari import ForbiddenError, NotFoundError
import lightbulb
from lightbulb import Client

from app.models import Events, Config, Stats_Deleted

from loguru import logger

loader = lightbulb.Loader()


@loader.task(lightbulb.uniformtrigger(minutes=15))
async def event_delete(client: Client) -> None:
    start = time.process_time()
    now = arrow.utcnow()

    guild_confs = await sync_to_async(Config.objects.filter)(delete_date=None)
    
    async for config in guild_confs:
        try:
            guild = await client.rest.fetch_guild(config.guild)
        except (NotFoundError, ForbiddenError):
            continue
        except:
            logger.warning(f"{sys.exc_info()}")
            continue
        
        events: QuerySet = await sync_to_async(Events.objects.filter)(gid=config)
        events = await sync_to_async(events.exclude)(delete_date=None)

        if not await sync_to_async(events.exists)():
            continue
        
        events: list[Events] = await sync_to_async(list)(events)
        
        for event in events:
            if arrow.get(event.delete_date).to('utc') <= now:
                await event.async_delete()
                
                # STATS
                try:
                    await sync_to_async(Stats_Deleted.objects.create)(gid=config.id)
                except:
                    logger.error(sys.exc_info())
                #
    
    logger.debug(f'Task \'event_delete\' took {time.process_time() - start}second(s) to complete')
