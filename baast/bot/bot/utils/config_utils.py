import sys
import asyncio
from asgiref.sync import sync_to_async

from hikari import Color, Embed, ComponentInteraction, Snowflakeish, TextableChannel
from lightbulb import Context, Client

from app.models import Config

from bot.bot.utils.exceptions import SetupCancel

from bot.bot.components.config_builder import ConfigBuilder

from loguru import logger


embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the command timedout.',
    color = Color(0xff0000)
)


async def RunConfigBuilder(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, 
                        config: Config) -> Config:
    try:
        selectObj:ConfigBuilder = await ConfigBuilder(snowflake, config).create(ctx)
        await ctx.edit_response(snowflake, selectObj.embed, components=selectObj)
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=300)
    except asyncio.TimeoutError:
        await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        raise SetupCancel
    
    if selectObj.newFeed:
        log_channel = selectObj.config.log_channel
        await client.rest.follow_channel("928620891041067028", log_channel)

    return await sync_to_async(Config.objects.get)(guild=int(ctx.guild_id))


