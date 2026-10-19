from functools import singledispatch

from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync

from hikari import ComponentInteraction, Guild, GuildChannel, GuildMessageDeleteEvent, RESTGuild, PartialGuild, PartialChannel, Role, Member, GatewayGuild
from lightbulb import Context

from loguru import logger

from cache.models import DiscordChannel, DiscordGuild, DiscordUser, DiscordRole

log = logger


def _safe_get_cache_view(cache_method, obj_name: str = "object"):
    """
    Safely get a cache view (members, channels, roles, etc.) and convert it to a list,
    handling race conditions where the cache dictionary might be modified during iteration.
    
    Args:
        cache_method: A callable that returns a cache view (e.g., guild.get_members)
        obj_name: Name of the object for logging purposes
    
    Returns:
        list: List of cached items, or empty list if unable to retrieve
    """
    max_retries = 5
    for attempt in range(max_retries):
        try:
            cache_view = cache_method()
            # Convert to list immediately to create a snapshot and avoid iteration issues
            return list(cache_view.values()) if hasattr(cache_view, 'values') else list(cache_view)
        except RuntimeError as e:
            error_msg = str(e)
            if "dictionary changed size during iteration" in error_msg:
                if attempt < max_retries - 1:
                    continue
                else:
                    log.warning(f"Failed to get cache view after {max_retries} attempts for {obj_name}: {error_msg}")
                    return []
            else:
                raise
        except Exception as e:
            log.warning(f"Error getting cache view for {obj_name}: {e}")
            return []
    return []


def _safe_get_member_count(guild_obj) -> int:
    """
    Safely get member count from a guild object, handling race conditions
    where the cache dictionary might be modified during iteration.
    
    Args:
        guild_obj: A guild object (Guild, GatewayGuild, RESTGuild, etc.)
    
    Returns:
        int: Member count, or 0 if unable to determine
    """
    if hasattr(guild_obj, 'approximate_member_count') and guild_obj.approximate_member_count is not None:
        return int(guild_obj.approximate_member_count)
    
    if hasattr(guild_obj, 'get_members'):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                members = guild_obj.get_members()
                return int(len(members))
            except RuntimeError as e:
                error_msg = str(e)
                if "dictionary changed size during iteration" in error_msg:
                    if attempt < max_retries - 1:
                        continue
                    else:
                        log.warning(f"Failed to get member count after {max_retries} attempts for guild {getattr(guild_obj, 'id', 'unknown')}: {error_msg}")
                        
                        if hasattr(guild_obj, 'approximate_member_count'):
                            return int(guild_obj.approximate_member_count or 0)
                        return 0
                else:
                    raise
            except Exception as e:
                log.warning(f"Error getting member count for guild {getattr(guild_obj, 'id', 'unknown')}: {e}")
                if hasattr(guild_obj, 'approximate_member_count'):
                    return int(guild_obj.approximate_member_count or 0)
                return 0
    return 0


@singledispatch
async def save_discord_meta_models(obj):
    return None

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: Guild | RESTGuild):
    log.debug("Creating discord guild from context")
    try:
        guild, _ = DiscordGuild.objects.update_or_create(
            discord_id=obj.id,
            defaults={
                        "discord_name": (obj.name),
                        "discord_icon_url": (obj.make_icon_url()),
                        "discord_owner_user": int(obj.owner_id), 
                        "discord_member_count": _safe_get_member_count(obj),
                        "has_app": True
                    },
        )
    except Exception as e:
        log.error(f"Error creating discord guild from context: {e}")
        raise e

    return guild

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: PartialGuild):
    log.debug("Creating partial discord guild from context")
    guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=obj.id,
        defaults={
                    "discord_name": (obj.name),
                    "discord_icon_url": (obj.make_icon_url()),
                    "discord_owner_user": 0, 
                    "discord_member_count": 0,
                    "has_app": True
                },
    )

    return guild

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: GatewayGuild):
    log.debug("Creating partial discord guild from context")
    guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=obj.id,
        defaults={
                    "discord_name": (obj.name),
                    "discord_icon_url": (obj.make_icon_url()),
                    "discord_owner_user": 0, 
                    "discord_member_count": 0,
                    "has_app": True
                },
    )

    return guild

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: Context):
    log.debug("Creating discord guild from context")
    _guild: RESTGuild = async_to_sync(obj.client.rest.fetch_guild)(obj.guild_id)
    _channel = _guild.get_channel(obj.channel_id)
    
    if not _channel:
        _channel = async_to_sync(obj.client.rest.fetch_channel)(obj.channel_id)
    
    try:
        guild, _ = DiscordGuild.objects.update_or_create(
            discord_id=int(obj.guild_id),
            defaults={
                        "discord_name": (_guild.name),
                        "discord_icon_url": (_guild.make_icon_url()),
                        "discord_owner_user": int(_guild.owner_id), 
                        "discord_member_count": _safe_get_member_count(_guild),
                        "has_app": True
                    },
        )
    except Exception as e:
        log.error(f"Error creating discord guild from context: {e}")
    
    try:
        channel, _ = DiscordChannel.objects.update_or_create(
            discord_id=int(obj.channel_id),
            defaults={
                        "name": _channel.name,
                    },
                discord_guild=guild,
            )
    except Exception as e:
        log.error(f"Error creating discord channel from context: {e}")

    try:
        user, _ = DiscordUser.objects.update_or_create(
            id=int(obj.user.id),
            defaults={
                        "name": obj.user.username
                    },
        )
    except Exception as e:
        log.error(f"Error creating discord user from context: {e}")
    else:
        try:
            if not user.discord_guilds.__contains__(int(obj.guild_id)):
                user.discord_guilds.append(int(obj.guild_id))
                user.save()
        except Exception as e:
            log.error(f"Error adding discord guild to user: {e}")

    return guild, channel, user#, message


@save_discord_meta_models.register
@database_sync_to_async
def _(obj: ComponentInteraction):
    log.debug("Creating discord guild from ComponentInteraction")
    guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=int(obj.guild_id),
        defaults={
            "discord_name": (obj.get_guild().name),
            "discord_icon_url": (obj.get_guild().make_icon_url()),
            "discord_owner_user": int(obj.get_guild().owner_id),
            "discord_member_count": _safe_get_member_count(obj.get_guild()),
            "has_app": True
        }
    )

    
    log.debug("Creating discord channel from ComponentInteraction")
    obj_channel = obj.channel
    channel, _ = DiscordChannel.objects.update_or_create(
        discord_id=int(obj.channel_id),
        defaults={
            "discord_guild": guild,
            "name": obj_channel.name,
        }
    )

    log.debug("Creating discord user from ComponentInteraction")
    user, _ = DiscordUser.objects.update_or_create(
        id=int(obj.user.id),
        defaults={
            "name": obj.user.username,
        }
    )
    
    if not user.discord_guilds.__contains__(int(obj.guild_id)):
        user.discord_guilds.append(int(obj.guild_id))
        user.save()
    
    return guild, channel, user

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: GuildMessageDeleteEvent):
    log.debug("Creating discord guild from GuildMessageDeleteEvent")
    _guild, _channel = None, None
    guild: GatewayGuild = obj.get_guild()
    member_count = _safe_get_member_count(guild)
    
    _guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=int(obj.guild_id),
        defaults={
            "discord_name": (guild.name),
            "discord_icon_url": (guild.make_icon_url()),
            "discord_owner_user": int(guild.owner_id),
            "discord_member_count": member_count,
            "has_app": True
        }
    )
    
    log.debug("Creating discord channel from GuildMessageDeleteEvent")
    obj_channel = obj.get_channel()
    if obj_channel:
        _channel, _ = DiscordChannel.objects.update_or_create(
                discord_id=int(obj.channel_id),
                defaults={
                "discord_guild": _guild,
                "name": obj_channel.name,
            }
        )

    return _guild, _channel

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: PartialChannel | GuildChannel, guild_obj: Guild):
    guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=int(guild_obj.id),
        defaults={
            "discord_name": (guild_obj.name),
            "discord_icon_url": (guild_obj.make_icon_url()),
            "discord_owner_user": int(guild_obj.owner_id),
            "discord_member_count": _safe_get_member_count(guild_obj),
        }
    )
    
    channel, _ = DiscordChannel.objects.update_or_create(
        discord_id=int(obj.id),
        defaults={
            "discord_guild": guild,
            "name": obj.name,
        }
    )

    return guild, channel

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: Role, guild_obj: Guild):
    guild, _ = DiscordGuild.objects.update_or_create(
        discord_id=int(guild_obj.id),
        defaults={
            "discord_name": (guild_obj.name),
            "discord_icon_url": (guild_obj.make_icon_url()),
            "discord_owner_user": int(guild_obj.owner_id),
            "discord_member_count": _safe_get_member_count(guild_obj),
        }
    )
    
    role, _ = DiscordRole.objects.update_or_create(
        discord_id=int(obj.id),
        defaults={
            "discord_name": obj.name,
            "discord_guild": guild,
        }
    )

    return guild, role

@save_discord_meta_models.register
@database_sync_to_async
def _(obj: Member):
    log.debug("Creating partial discord member from context")
    
    if obj.global_name is None:
        log.debug(f"No Non Null Name For User: {obj.id}")
        return None
    else:
        try:
            guild, _ = DiscordUser.objects.update_or_create(
                id=obj.id,
                defaults={
                                "name": obj.global_name
                            },
            )
        except Exception as e:
            log.error(f"Error creating discord user from context: {e}")
            return None

        return guild

def GetGuild(id: int) -> DiscordGuild:
    try:
        guild = DiscordGuild.objects.get(
            discord_id=id,
        )
    except DiscordGuild.DoesNotExist:
        logger.debug(f"NO GUILD WITH THIS ID: {id}")
        raise DiscordGuild.DoesNotExist
    else:
        return guild
    return None

def GetChannel(id: int) -> DiscordChannel:
    try:
        channel = DiscordChannel.objects.get(
            discord_id=id,
        )
    except DiscordChannel.DoesNotExist:
        logger.debug(f"NO CHANNEL WITH THIS ID: {id}")
    else:
        return channel
    return None

def GetUser(id: int) -> DiscordUser:
    try:
        user = DiscordUser.objects.get(
            id=id,
        )
    except DiscordUser.DoesNotExist:
        raise DiscordUser.DoesNotExist
    else:
        return user

def GetGuilds() -> list[DiscordGuild]:
    try:
        guilds = DiscordGuild.objects.all()
    except DiscordGuild.DoesNotExist:
        logger.debug("NO GUILDS IN CACHE")
    else:
        return guilds
    return None

def GetGuildChannels(id: int) -> list[DiscordChannel]:
    try:
        channels = DiscordChannel.objects.filter(
            discord_guild=id,
        )
    except DiscordChannel.DoesNotExist:
        logger.debug(f"GUILD HAS NO CHANNELS?: {id}")
    else:
        return channels
    return None

def GetGuildRoles(id: int) -> list[DiscordRole]:
    if DiscordRole.objects.filter(discord_guild_id=id).exists():
        return DiscordRole.objects.filter(discord_guild_id=id)
    else:
        return None