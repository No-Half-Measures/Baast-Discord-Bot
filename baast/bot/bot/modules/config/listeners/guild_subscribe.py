from datetime import datetime, UTC
from hikari import EntitlementCreateEvent, EntitlementDeleteEvent, EntitlementUpdateEvent 
import lightbulb
from asgiref.sync import sync_to_async

from app.models import Config

from loguru import logger


loader = lightbulb.Loader()


@loader.listener(EntitlementCreateEvent)
async def guild_subscribe_interaction(evt: EntitlementCreateEvent) -> None:
    entitlement = evt.entitlement
    if entitlement.guild_id is None:
        return
    
    if entitlement.sku_id != 1392892692543045815:
        logger.warning(f'Guild **{entitlement.guild_id}** used incorrect SKU {entitlement.sku_id} for Baast...')
        return
    
    guild = await evt.app.rest.fetch_guild(entitlement.guild_id)
    
    if guild is None:
        logger.warning(f'Guild **{entitlement.guild_id}** not found in Discord...')
        return
    
    config: Config = await sync_to_async(Config.objects.get)(guild=entitlement.guild_id)
    
    config.p_expire_date = entitlement.ends_at
    await config.asave()
    
    logger.info(f'Guild **{guild.name}** : `{guild.id}` - Subscribed to Baast')
    

@loader.listener(EntitlementUpdateEvent)
async def guild_subscribe_interaction(evt: EntitlementUpdateEvent) -> None:
    entitlement = evt.entitlement
    if entitlement.guild_id is None:
        return
    
    if entitlement.sku_id != 1392892692543045815:
        logger.warning(f'Guild **{entitlement.guild_id}** used incorrect SKU {entitlement.sku_id} for Baast...')
        return
    
    guild = await evt.app.rest.fetch_guild(entitlement.guild_id)
    
    if guild is None:
        logger.warning(f'Guild **{entitlement.guild_id}** not found in Discord...')
        return
    
    config: Config = await sync_to_async(Config.objects.get)(guild=entitlement.guild_id)
    
    config.p_expire_date = entitlement.ends_at
    await config.asave()
    
    logger.info(f'Guild **{guild.name}** : `{guild.id}` - continued the subscription to Baast')
    

# Rare but happens on refunds or if discord removes it.
@loader.listener(EntitlementDeleteEvent)
async def guild_subscribe_interaction(evt: EntitlementDeleteEvent) -> None:
    entitlement = evt.entitlement
    if entitlement.guild_id is None:
        return
    
    if entitlement.sku_id != 1392892692543045815:
        logger.warning(f'Guild **{entitlement.guild_id}** used incorrect SKU {entitlement.sku_id} for Baast...')
        return
    
    guild = await evt.app.rest.fetch_guild(entitlement.guild_id)
    
    if guild is None:
        logger.warning(f'Guild **{entitlement.guild_id}** not found in Discord...')
        return
    
    default = Config().reminders

    config: Config = await sync_to_async(Config.objects.get)(guild=entitlement.guild_id)
    config.backup_reminders = config.reminders
    config.reminders = default
    config.save()
    
    config.p_expire_date = datetime.now(UTC)
    await config.asave()
    
    logger.info(f'Guild **{guild.name}** : `{guild.id}` - Either Refunded or Discord Removed from Baast')
    
    