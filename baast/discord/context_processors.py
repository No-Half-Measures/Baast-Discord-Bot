import sys
from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from discord.hashids import Hashids
from django.conf import settings

from app.models import Events, Config, Events_Links

from loguru import logger

SALT = getattr(settings, 'HASH_SALT', None)

def nav_data(request: HttpRequest):
    url_path = request.path
    parts = url_path.strip('/').split('/')
    
    nav_data = {}

    if getattr(request, 'site_section', '') == 'panel':
        guild_data: dict = getattr(request, 'guild_data', {})
        
        hashids = Hashids(salt=SALT)
        guild_id = hashids.decode(guild_data['hash'])[0]
        
        conf: Config = Config.objects.get(guild=guild_id)

        nav_data["hash"] = guild_data['hash']
        nav_data["conf"] = conf

    if getattr(request, 'site_section', '') == 'panel_home' or getattr(request, 'site_section', '') == 'panel' or getattr(request, 'site_section', '') == 'panel_user':
        # Get data from request object that was set by middleware
        nav_data["nav_guilds"] = getattr(request, 'nav_guilds', None)
        nav_data["nav_user"] = getattr(request, 'nav_user', None)
        
    return { 'nav_data': nav_data }
