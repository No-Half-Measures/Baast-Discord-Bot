import sys
import arrow

from asgiref.sync import sync_to_async

from hikari import ForbiddenError, GuildLeaveEvent, MessageFlag
import lightbulb

from app.models import Config, Stats_Leave
from cache.models import DiscordGuild
from bot.bot.components.help_components import LeaveComponents


from loguru import logger


loader = lightbulb.Loader()



@loader.listener(GuildLeaveEvent)
async def guildleave_interaction(evt: GuildLeaveEvent) -> None:
    guild = evt.old_guild
    
    if guild == None:
        return
    
    try:
        config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
    except Config.DoesNotExist:
        logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
        return
    
    # MESSAGE OWNER ASK FOR FEEDBACK
    try:
        dm_channel = await evt.app.rest.create_dm_channel(guild.owner_id)
        await evt.app.rest.create_message(dm_channel, components=LeaveComponents, flags=MessageFlag.IS_COMPONENTS_V2)
    except ForbiddenError:
        pass
    except:
        logger.error(sys.exc_info())
    
    # STATS
    try:
        await sync_to_async(Stats_Leave.objects.create)()
    except:
        logger.error(sys.exc_info())
    #
    
    try:
        config.delete_date = arrow.utcnow().shift(days=30).datetime
        await config.asave()
    except:
        logger.error(sys.exc_info())
    
    
    try:
        _guild = await sync_to_async(DiscordGuild.objects.get)(discord_id=int(guild.id))
    except DiscordGuild.DoesNotExist:
        logger.warning(f'Guild {guild.name}:{guild.id} does not exist in the database')
    else:
        _guild.has_app = False
        await _guild.asave()
        
    
    logger.info(f'Left the Guild **{guild.name}** : `{guild.id}`')
    