import asyncio
import logging

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.utils.decorators import classonlymethod
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from discord.hashids import Hashids
from discord.pages.ajax.base import BaseAjaxView

from app.models import Templates, Config, Option_Presets


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxOptions(BaseAjaxView):
    http_method_names = ['GET']
    # GET
    async def get(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response
        
        try:
            options_list = []
            if 'template' in kwargs:
                # Get options by template ID
                template_id = int(kwargs['template'])
                template: Templates = await sync_to_async(Templates.objects.get)(id=template_id)
                
                try:
                    tconf = await sync_to_async(template.Config)()
                except Config.DoesNotExist:
                    return JsonResponse({"error": "Error."}, status=400)
                
                if tconf.id != config.id and tconf.id != 1:
                    return JsonResponse({"error": "This guild does not have access to this template"}, status=400)
                
                options_list = await sync_to_async(template.get_options)()
                
                options = []
                for option in options_list:
                    labels = ""
                    for o in option.options:
                        labels += f"{o['label']}, "
                    options.append({
                        "id": option.id,
                        "name": option.name,
                        "use_capacity": option.use_capacity,
                        "label": labels,
                    })
                
            elif 'option' in kwargs:
                # Get option directly by ID
                option_id = int(kwargs['option'])
                try:
                    option = await sync_to_async(Option_Presets.objects.get)(id=option_id)
                except Option_Presets.DoesNotExist:
                    return JsonResponse({"error": "Option not found"}, status=404)
                
                options = {
                    "id": option.id,
                    "name": option.name,
                    "label": option.to_string,
                    "options": option.options
                }
                
            return JsonResponse({ "success": "", "options" : options }, status=200, content_type="application/json")
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxOptions: {e}")
            return redirect('/login/')
