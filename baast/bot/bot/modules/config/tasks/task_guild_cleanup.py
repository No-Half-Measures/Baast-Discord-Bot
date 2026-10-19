import sys, arrow
from datetime import timedelta
from asgiref.sync import sync_to_async

from hikari import ForbiddenError, NotFoundError
from lightbulb import Client, uniformtrigger, Loader

from app.models import Config

from loguru import logger


loader = Loader()
@loader.task(uniformtrigger(hours=12, wait_first=False))
async def task_guild_cleanup(client: Client) -> None:
    guild_confs = await sync_to_async(Config.objects.filter)(delete_date=None)

    async for config in guild_confs:
        try:
            guild = await client.rest.fetch_guild(config.guild)
        except (NotFoundError, ForbiddenError):
            if config.delete_date == None:
                config.delete_date = arrow.utcnow().shift(days=7).datetime
                await config.asave()
            continue
        except:
            logger.warning(f"{sys.exc_info()}")
            continue
        
        if config.delete_date != None:
            now = arrow.utcnow()
            
            if arrow.get(config.delete_date).to('utc') <= now:
                try:
                    await config.adelete()
                except:
                    logger.error(sys.exc_info())
                    continue
                
                logger.info(f'Baast cleaned up Guild `{config.guild}`')
