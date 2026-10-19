import sys
import asyncio
import logging
from typing import List
from datetime import datetime, timedelta
import pytz

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models.query import QuerySet

from hikari import RESTApp, OwnUser, Embed, Color, UnauthorizedError

from discord.pages.ajax.base import BaseAjaxView
from discord.hashids import Hashids

from bot.bot.modules.events.classes.sheet import Sheet

from app.models import Config, Events, Attendance, Stats_Deleted

from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxEventDelete(BaseAjaxView):
    http_method_names = ['POST']
    # GET
    async def post(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        event_id = kwargs['id']
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response
        
        try:
            restapp = await self.get_restapp(access_token)
            try:
                async with restapp.acquire(access_token, "BEARER") as bearer:
                    author: OwnUser = await bearer.fetch_my_user()
            finally:
                await self.release_restapp(access_token, restapp)
            
            try:
                event: Events = await sync_to_async(Events.objects.get)(gid=config, id=event_id)
            except  Events.DoesNotExist:
                return redirect(reverse('discord:dash_overview', kwargs={'hashguild':guild_hash}))
            
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.send('discord', {'type': 'delete.event', 'id': event.id, 'user_id': author.id})
            
            return JsonResponse({"success": ""}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxEventDelete: {e}")
            return redirect('/login/')
