import asyncio
import logging

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db import models

from discord.hashids import Hashids
from discord.guild_mixin import GuildMixin

from app.models import Config, Templates, Option_Presets


from loguru import logger


class TemplatesView(GuildMixin, View):
    template_name = 'discord/dash_templates.html'
    
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
        
        # Now we have guild_data.guild_id, guild_data.config, etc.
        try:
            templates = await self._get_templates(guild_data.config, guild_data.guild_id)
            options = await sync_to_async(Option_Presets.objects.all)()
            
            return await sync_to_async(render)(request, self.template_name, context={
                "templates": templates,
                "options": options,
            })
            
        except Exception as e:
            logger.error(f"Error in TemplatesView.get: {e}")
            return JsonResponse({"error": "Internal server error"}, status=500)
    

    async def _get_templates(self, config: Config, guild_id: int):
        """Fetch templates for the guild."""
        try:
            # Get guild-specific templates
            templates = await sync_to_async(lambda: list(Templates.objects.filter(gid=config.id)))()
            
            # Add global templates (excluding the current guild)
            if guild_id != MAIN_GUILD_ID:  # Replace with your global guild ID
                try:
                    global_template = await sync_to_async(lambda: Templates.objects.get(id=1))()
                    templates.append(global_template)
                except Templates.DoesNotExist:
                    logger.warning("Global template not found")
            
            return templates
            
        except Exception as e:
            logger.error(f"Error fetching templates: {e}")
            return []

