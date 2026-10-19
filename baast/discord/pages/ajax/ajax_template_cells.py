import asyncio
import logging
import sys

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

from discord.pages.ajax.base import BaseAjaxView
from discord.hashids import Hashids

from app.models import Config, Option_Presets, Templates


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxPresetCells(BaseAjaxView):
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
                
            # Get Template
            try:
                obj:Templates = await sync_to_async(Templates.objects.get)(gid=config, id=id)
            except Templates.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
                return JsonResponse({"error": "Unkown Error"}, status=400)
            
            # Get Preset
            try:
                presets = await sync_to_async(Option_Presets.objects.get)(gid=config, id=pid)
            except Templates.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
                return JsonResponse({"error": "Unkown Error"}, status=400)
            
            cell_labels: dict = {}
            
            if type(obj.cells) == list:
                print("Is same type")
                obj.cells = {}
            
            if pid.__str__() not in obj.cells.keys():
                obj.cells[pid.__str__()] = {}
            
            for option in presets.options:
                cell_labels[option['label']] = obj.cells[pid.__str__()][option['label']] if option['label'] in obj.cells[pid.__str__()].keys() else 'None'
            
            await obj.asave()
            
            return JsonResponse({ "status": "success", "cells_labels": cell_labels }, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in GET:AjaxPresetCells: {e}")
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

            # Get Data and break it down
            data = request.POST.dict()
            
            # Get Template
            try:
                obj = await sync_to_async(Templates.objects.get)(gid=config, id=id)
            except Templates.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
                return JsonResponse({"error": "Unkown Error"}, status=400)
            
            # Get Preset
            try:
                preset_obj:Option_Presets = await sync_to_async(Option_Presets.objects.get)(gid=config, id=pid)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
                return JsonResponse({"error": "Unkown Error"}, status=400)
            
            obj.cells[pid] = {}
            for option in  preset_obj.options:
                obj.cells[pid][option['label']] = data[option['label']]
            
            await obj.asave()
            
            return JsonResponse({ "status": "success"}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in POST:AjaxPresetCells: {e}")
            return redirect('/login/')
