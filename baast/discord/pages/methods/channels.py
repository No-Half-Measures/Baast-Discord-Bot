import time
import logging
from typing import Sequence

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.utils.decorators import classonlymethod
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from discord.hashids import Hashids
from hikari import RESTApp, Permissions, GuildChannel, GuildTextChannel, ChannelType, PermissionOverwrite, TextableGuildChannel, Member

from channels.layers import get_channel_layer
from cache.helpers import GetGuildChannels

from cache.models import DiscordChannel
from app.models import Config


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')


class Channels():
    @classonlymethod
    async def get(cls, guildid) -> DiscordChannel:
        cachedChannel = None
        timeout = 1   # [seconds]
        timeout_start = time.time()

        while time.time() < timeout_start + timeout and cachedChannel is None:
            try:
                cachedChannel = await sync_to_async(GetGuildChannels)(guildid)
            except DiscordChannel.DoesNotExist:
                channel_layer = get_channel_layer()
                await channel_layer.send('discord', {'type': 'get.guild.channels', 'id': int(guildid)})
                time.sleep(0.75)
        
        return cachedChannel