import asyncio
import logging
import sys

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound

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

class AjaxTemplate(BaseAjaxView):
    async def post(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        id = int(kwargs['id'])
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response
        
        restapp = await self.get_restapp(access_token)
        try:
            async with restapp.acquire(access_token, "BEARER") as bearer:
                author: OwnUser = await bearer.fetch_my_user()
        finally:
            await self.release_restapp(access_token, restapp)
        
        try:
            # Get Data and break it down
            data = request.POST.dict()
            
            # create/update
            name = data['name']
            title = data['title'] if 'title' in data.keys() and data['title'] != 'None' else None
            description = data['description'] if 'description' in data.keys() and data['description'] != 'None' else None
            # update
            thumb = data['thumb'] if 'thumb' in data.keys() and data['thumb'] != 'None' else None
            emoji = data['emoji'] if 'emoji' in data.keys() else None
            sheetid = data['sheetid'] if 'sheetid' in data.keys() and data['sheetid'] != 'None' else None
            worksheetid = data['worksheetid'] if 'worksheetid' in data.keys() and data['worksheetid'] != 'None' else None
            
            cell_title = data['cell_title'] if 'cell_title' in data.keys() else None
            cell_desc = data['cell_desc'] if 'cell_desc' in data.keys() else None
            cell_date = data['cell_date'] if 'cell_date' in data.keys() else None
            cell_link = data['cell_link'] if 'cell_link' in data.keys() else None
            
            
            # Validation
            # Check title length
            if len(name) == 0:
                logger.info("Name is blank! Try Again...")
                return JsonResponse({"error": "Name is blank! Try Again..."}, status=400)
            if len(name) > 100 :
                logger.info("Name is too long! Try Again...")
                return JsonResponse({"error": "Name is too long! Try Again..."}, status=400)
            
            # Get
            try:
                obj = await sync_to_async(Templates.objects.get)(gid=config, id=id)
                
                cell_data = obj.cells
                cell_data['cell_title'] = cell_title
                cell_data['cell_desc'] = cell_desc
                cell_data['cell_date'] = cell_date
                cell_data['cell_link'] = cell_link
                
                obj.name = name
                obj.title = title
                obj.description = description
                obj.thumb_url = thumb
                obj.emoji = emoji
                obj.sheetid = sheetid
                obj.worksheetid = worksheetid
                
                obj.cells = cell_data
                
                await obj.asave()
                
            except Templates.DoesNotExist:
                try:
                    obj  = await sync_to_async(Templates.objects.create)(
                        gid = config,
                        name = name,
                        sheetid = sheetid,
                        title = title,
                        description = description,
                        )
                except Exception as e:
                    logger.error(f"Error in AjaxTemplate: {e}")
                    return JsonResponse({"error": f"Unable to {id == -1: 'create' else 'update'} Template"}, status=400)
            except Exception as e:
                logger.error(f"Error in AjaxTemplate: {e}")
                return JsonResponse({"error": f"Unable to {id == -1: 'create' else 'update'} Template"}, status=400)
            
            has_Access = False
            try:
                has_Access = obj.hasSheetAccess
            except:
                logger.error(sys.exc_info())
            
            return JsonResponse({ "status": "success", "id": obj.id, "hasAccess": has_Access}, status=200)
        except Exception as e:
            logger.error(f"Error in AjaxTemplate: {e}")
            return redirect('/login/')
        return JsonResponse({"error": "AJAX Error"}, status=400)
