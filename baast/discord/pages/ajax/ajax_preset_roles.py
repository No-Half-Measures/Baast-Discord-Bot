import asyncio
import logging
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

class AjaxPresetRoles(BaseAjaxView):
    async def get(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        
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
                
            preset_id = int(kwargs['preset'])
            
            
            try:
                option: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=preset_id)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            
            if 'roleset' in kwargs:
                roleset_id = int(kwargs['roleset'])
                
                try:
                    preset_roles: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id=roleset_id, gid=config, preset=option)
                except Preset_Roles.DoesNotExist:
                    return redirect(reverse('discord:dash_home'))
                
                roleset_json = {
                    "id": preset_roles.id,
                    "name": preset_roles.name,
                    "roles": preset_roles.roles
                }
            else:
                try:
                    preset_roles: Preset_Roles = await sync_to_async(list)(Preset_Roles.objects.filter(gid=config, preset=option))
                except Preset_Roles.DoesNotExist:
                    return redirect(reverse('discord:dash_home'))
                
                roleset_json = []
                
                for role in preset_roles:
                    roleset_json.append({
                        "id": role.id,
                        "name": role.name,
                        "roles": role.roles
                    })
            
            return JsonResponse({ "status": "success", "roleset": roleset_json }, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in GET:AjaxPresetRoles: {e}")
            return redirect('/login/')

    
    
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
                
            preset_id = int(kwargs['preset'])
            roleset_id = int(kwargs['roleset'])
            
            try:
                option: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=preset_id)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            
            # Get Data and break it down
            data = json.loads(request.body)
            
            name = data['name']
            roles = data['roles']
            
            try:
                role_obj = []
                for role in roles:
                    index = int(role['index'])
                    role_id = int(role['role_id']) if role['role_id'].lower() != 'none' else 'none'
                    role_name = role['role_name']
                    
                    logger.info(f"Index: {index}, Role ID: {role_id}, Role Name: {role_name}")
                    
                    role_obj.append({
                        "index": index,
                        "role_id": str(role_id),
                        "role_name": role_name
                    })
            except Exception as e:
                logger.error(f"Error: {e}")
                return JsonResponse({"error": e}, status=400)
            
            try:
                preset_roles: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id=roleset_id, gid=config)
            except Preset_Roles.DoesNotExist:
                preset_roles: Preset_Roles = await sync_to_async(Preset_Roles.objects.create)(gid=config, preset=option, name=name, roles=role_obj)
            except Exception as e:
                logger.error(f"Error: {e}")
                return JsonResponse({"error": e}, status=400)
            else:
                preset_roles.name = name
                preset_roles.roles = role_obj
                await preset_roles.asave()
            
            
            return JsonResponse({ "status": "success", "index": preset_roles.id, "html": preset_roles.to_html}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in POST:AjaxPresetRoles: {e}")
            return redirect('/login/')
