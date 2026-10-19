from datetime import datetime, timedelta
import pytz
import asyncio
import logging
import time

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from hikari import RESTApp, UnauthorizedError, NotFoundError

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles
from discord.hashids import Hashids

from app.models import Events, Config, Attendance, Option_Presets


from loguru import logger


class PresetsView(GuildMixin, View):
    template_name = 'discord/dash_presets.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return async_to_sync(view)

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        guild_data, error_response = await self.validate_guild_request(request, kwargs)
        if error_response:
            return error_response
        
        #
        # Global Options
        #
        global_options = None
        if guild_data.guild_id != MAIN_GUILD_ID:
            try:
                global_conf: Config = await sync_to_async(Config.objects.get)(guild=MAIN_GUILD_ID)
            except Config.DoesNotExist:
                logger.error(f"Baast Support Guild not found.")
            else:
                global_options = await sync_to_async(Option_Presets.objects.filter)(gid=global_conf)
        # 
            
        options_ = await sync_to_async(Option_Presets.objects.filter)(gid=guild_data.config)
        options = []
        
        options = await sync_to_async(list)(global_options)  
        options.extend(await sync_to_async(list)(options_))
        
        return await sync_to_async(render)(request, self.template_name, context={
            "presets" : options,
        })

