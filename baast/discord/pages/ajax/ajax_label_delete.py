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

from discord.hashids import Hashids
from discord.pages.ajax.base import BaseAjaxView

from app.models import Config, Option_Presets


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxLabelDelete(BaseAjaxView):
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
            # Get Data and break it down
            data = request.POST.dict()
            
            index = int(data['index'])
            
            # Get Options
            try:
                options: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=id, gid=config)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
            
            if int(index) != -1:
                try:
                    options.options.pop(index)
                except:
                    return JsonResponse({"error": "Error"}, status=400)
            else:
                return JsonResponse({"error": "Error"}, status=400)
            
            await options.asave()  
            return JsonResponse({ "status": "success", "index": index}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxLabelDelete: {e}")
            return redirect('/login/')
