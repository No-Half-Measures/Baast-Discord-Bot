import sys
from hikari import GuildChannelDeleteEvent, UnauthorizedError
import lightbulb
from asgiref.sync import sync_to_async

from app.models import Config, Stats_Join


from loguru import logger


loader = lightbulb.Loader()


@loader.listener(GuildChannelDeleteEvent)
async def guildchanneldelete_interaction(evt: GuildChannelDeleteEvent) -> None:
    guild = evt.get_guild()
    
    if guild == None:
        return
    
    config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
    
    if config.log_channel == evt.channel_id:
        config.log_channel = None
        
    if evt.channel_id in config.event_channels:
        config.event_channels.remove(evt.channel_id)
        
    await config.asave()
    