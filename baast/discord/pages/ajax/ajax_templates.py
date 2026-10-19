import asyncio
import logging

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.utils.decorators import classonlymethod
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from discord.pages.ajax.base import BaseAjaxView
from discord.hashids import Hashids

from app.models import Templates, Config


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')

class AjaxTemplates(BaseAjaxView):
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
            # Get templates using connection pool (if needed for Discord API calls)
            # For this specific view, we only need database access
            defaults = await sync_to_async(Templates.objects.filter)(gid=1)
            guild_templates = await sync_to_async(Templates.objects.filter)(gid=config)
            
            templates_list = await sync_to_async(list)(guild_templates | defaults)
            
            templates = []
            for template in templates_list:
                templates.append({
                    "id": template.id,
                    "name": template.name
                })

            return JsonResponse({
                "success": "", 
                "templates": templates
            }, status=200, content_type="application/json")
            
        except Exception as e:
            logger.error(f"Error getting templates: {e}")
            return JsonResponse({"error": "Failed to get templates"}, status=500)
