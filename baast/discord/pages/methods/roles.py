import time

from asgiref.sync import sync_to_async

from django.utils.decorators import classonlymethod

from channels.layers import get_channel_layer
from cache.helpers import GetGuildRoles


class Roles():
    @classonlymethod
    async def get(cls, guildid):
        cachedRoles = None
        timeout = 2   # [seconds]
        timeout_start = time.time()

        while time.time() < timeout_start + timeout and cachedRoles is None:
            cachedRoles = await sync_to_async(GetGuildRoles)(guildid)
            
            if cachedRoles == None:
                channel_layer = get_channel_layer()
                await channel_layer.send('discord', {'type': 'get.guild.roles', 'id': str(guildid)})
                time.sleep(1)
        
        return cachedRoles