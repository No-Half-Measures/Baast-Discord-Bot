import sys
from hikari import GuildJoinEvent, MessageFlag, ForbiddenError
import lightbulb
from asgiref.sync import sync_to_async

from app.models import Config, Stats_Join
from cache.helpers import _safe_get_member_count

from bot.bot.components.help_components import WelcomeComponents

from loguru import logger


loader = lightbulb.Loader()


@loader.listener(GuildJoinEvent)
async def guildjoin_interaction(evt: GuildJoinEvent) -> None:
    guild = evt.get_guild()
    
    if guild == None:
        return
    
    try:
        owner = await guild.fetch_owner()
    except Exception as e:
        logger.error(f"GuildJoin: {guild.id} - {e} (Probably join event triggering late)")
        return
    
    member_count = _safe_get_member_count(guild)
    
    try:
        config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
    except Config.DoesNotExist:
        logger.info(f'Joined a New Guild **{guild.name}** : `{guild.id}` - {member_count} Members - Owner : {owner.mention}')

        try:
            await sync_to_async(Config.objects.create)(guild=int(guild.id))
        except:
            logger.error(sys.exc_info())
    else:
        config.delete_date = None
        await config.asave()
        logger.info(f'Joined Guild **{guild.name}** : `{guild.id}`- {member_count} Members  - Owner : {owner.mention}')

    
    #########################################################
    # DM Owner With Info & Help
    #########################################################
    try:
        await owner.send(components=WelcomeComponents, flags=MessageFlag.IS_COMPONENTS_V2)
    except ForbiddenError:
        pass
    except Exception as e:
        logger.error(f'Error sending welcome message to owner of guild {guild.name}:{guild.id}: {e}')
    #########################################################
        
    # STATS
    try:
        await sync_to_async(Stats_Join.objects.create)()
    except Exception as e:
        logger.error(f'Error creating stats join for guild {guild.name}:{guild.id}: {e}')
