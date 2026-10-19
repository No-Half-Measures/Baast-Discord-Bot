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

from app.models import Config, Option_Presets, Preset_Roles


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxLabel(BaseAjaxView):
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
            
            label = data['label']
            colour = data['colour']
            index = int(data['index'])
            
            attendingToggle = (data['attendingToggle'].lower() == 'true')
            tentativeToggle = (data['tentativeToggle'].lower() == 'true')
            notieToggle = (data['notieToggle'].lower() == 'true')
            
            
            # Validation
            # Check title length
            if len(label) == 0:
                logger.info("Label is blank! Try Again...")
                return JsonResponse({"error": "Label is blank! Try Again..."}, status=400)
            if len(label) > 100:
                logger.info("Label is too long! Try Again...")
                return JsonResponse({"error": "Label is too long! Try Again..."}, status=400)
            
            # Get Options
            try:
                options: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=id, gid=config)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            except:
                logger.info(sys.exc_info())
                return JsonResponse({"error": "Error"}, status=400)
            
            if options.options.__len__() >= 9:
                return JsonResponse({"error": "There are already 9 max options."}, status=400)
            
            if int(index) != -1:
                options.options[index]['label'] = label
                options.options[index]['colour'] = colour
                options.options[index]['is_attending'] = attendingToggle
                options.options[index]['istentative'] = tentativeToggle
                options.options[index]['send_notifcations'] = notieToggle    
            else:
                options.options.append({"label": label, "colour": colour, "is_attending": attendingToggle, "istentative": tentativeToggle, "send_notifcations": notieToggle})
                index = len(options.options) - 1
            
            await options.asave()  
            return JsonResponse({ "status": "success", "index": index, "maxOptions": options.options.__len__() >= 9}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxLabel: {e}")
            return redirect('/login/')
