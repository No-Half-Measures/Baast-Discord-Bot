import asyncio
import logging
import sys
import json

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from hikari import OwnUser, RESTApp

from discord.hashids import Hashids
from discord.pages.ajax.base import BaseAjaxView

from app.models import Config, Option_Presets, Preset_Roles


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxPreset(BaseAjaxView):
    async def post(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response
                
        if not config.is_premium:
            return JsonResponse({"error": "Not Premium"}, status=400)
                
        try:
            restapp = await self.get_restapp(access_token)
            try:
                async with restapp.acquire(access_token, "BEARER") as bearer:
                    author: OwnUser = await bearer.fetch_my_user()
            finally:
                await self.release_restapp(access_token, restapp)

            data = json.loads(request.body)
                
                
            preset_ID = int(kwargs['id'])
            
            # Get Data and break it down
            data = request.POST.dict()
            
            name = data['name']
            capToggle = (data['capToggle'].lower() == 'true')
            splitCapToggle = (data['splitCapToggle'].lower() == 'true')
            
            if preset_ID == -1:
                # Validation
                # Check title length
                if len(name) == 0:
                    logger.info("Name is blank! Try Again...")
                    return JsonResponse({"error": "Name is blank! Try Again..."}, status=400)
                if len(name) > 100 :
                    logger.info("Name is too long! Try Again...")
                    return JsonResponse({"error": "Name is too long! Try Again..."}, status=400)
                
                # Get Options
                try:
                    preset = await sync_to_async(Option_Presets.objects.create)(
                        gid = config,
                        name = name,
                        options = [],
                        len = 0,
                        use_capacity = capToggle,
                        split_capacity = splitCapToggle
                    )
                except:
                    logger.info(sys.exc_info())
                    return JsonResponse({"error": "Unable to create Preset"}, status=400)
            else:
                
                try:
                    preset = await sync_to_async(Option_Presets.objects.get)(id=preset_ID, gid=config)
                except:
                    return redirect(reverse('discord:dash_home'))
                
                order = json.loads(data['order'])
                
                # Convert order list of string to list of integers
                order = [int(x) for x in order]
                
                # Reorder preset options based on new order
                current_options = preset.options
                reordered_options = [current_options[old_index] for old_index in order]
                preset.options = reordered_options
                
                # Reorder preset roles
                preset_roles_list = await sync_to_async(list)(Preset_Roles.objects.filter(preset=preset))
                for preset_roles in preset_roles_list:
                    current_roles = preset_roles.roles
                    reordered_roles = [current_roles[old_index] for old_index in order]
                    preset_roles.roles = reordered_roles
                    await preset_roles.asave()
                
                
                preset.name = name
                preset.use_capacity = capToggle
                preset.split_capacity = splitCapToggle
                
                await preset.asave()
            
            return JsonResponse({ "status": "success", "id": preset.id}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxPreset: {e}")
            return redirect('/login/')
