import asyncio
import logging
from typing import Optional, Tuple, Any

from asgiref.sync import sync_to_async, async_to_sync
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import classonlymethod
from django.views import View
from django.views.decorators.csrf import csrf_protect
from hikari import RESTApp, TokenType

from discord.mixins import DiscordAuthMixin
from discord.hashids import Hashids
from django.conf import settings

from loguru import logger

SALT = getattr(settings, 'HASH_SALT', None)

class BaseAjaxView(View, DiscordAuthMixin):
    """
    Base class for all AJAX views with integrated connection pooling.
    Provides common authentication, validation, and Discord client management.
    """
    
    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return async_to_sync(view)
    
    async def dispatch(self, request: HttpRequest, *args, **kwargs):
        """Override dispatch to add common AJAX handling."""
        # Check if it's an AJAX request
        if not await sync_to_async(request.headers.get)('X-Requested-With') == 'XMLHttpRequest':
            logger.warning(f"AJAX request required: {request.headers.get('X-Requested-With')}")
            return JsonResponse({"error": "AJAX request required"}, status=400)
        
        # Validate session
        access_token, error_response = await self.validate_session(request)
        if error_response:
            return error_response
        
        # Add access_token to kwargs for use in view methods
        kwargs['access_token'] = access_token
        
        # Call the appropriate method (get, post, etc.) directly instead of super().dispatch
        # This avoids the issue with HttpResponseNotAllowed not being awaitable
        method = request.method.lower()
        if hasattr(self, method):
            handler = getattr(self, method)
            return await handler(request, *args, **kwargs)
        else:
            # Method not allowed
            return JsonResponse({"error": "Method not allowed"}, status=405)
    
    async def get_guild_config(self, hashguild: str) -> Tuple[Optional[Any], Optional[JsonResponse]]:
        """
        Get guild configuration from hashguild parameter.
        Returns: (config, error_response)
        """
        try:
            hashids = Hashids(salt=SALT)
            guild_id = hashids.decode(hashguild)[0]
        except Exception as e:
            logger.error(f"Error decoding guild hash: {e} ({hashguild})")
            return None, JsonResponse({"error": "Invalid Guild ID"}, status=400)
        
        try:
            from app.models import Config
            config = await sync_to_async(Config.objects.get)(guild=guild_id)
            return config, None
        except Exception as e:
            logger.error(f"Error getting guild config: {e}")
            return None, JsonResponse({"error": "Guild not found"}, status=404)
    
    async def get_discord_user(self, access_token: str, request: HttpRequest) -> Tuple[Optional[Any], Optional[JsonResponse]]:
        """
        Get Discord user information.
        Returns: (user, error_response)
        """
        try:
            async with self.with_discord_client(access_token) as (restapp, client):
                async with client as bearer:
                    from discord.OAuth2 import DUser
                    user = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
                    return user, None
        except Exception as e:
            logger.error(f"Error getting Discord user: {e}")
            return None, JsonResponse({"error": "Failed to get user information"}, status=500)
    
    async def handle_discord_api_error(self, error: Exception) -> JsonResponse:
        """Handle Discord API errors consistently."""
        if hasattr(error, 'status_code'):
            if error.status_code == 401:
                return JsonResponse({"error": "Session expired, please login again"}, status=401)
            elif error.status_code == 403:
                return JsonResponse({"error": "Insufficient permissions"}, status=403)
            elif error.status_code == 404:
                return JsonResponse({"error": "Resource not found"}, status=404)
        
        logger.error(f"Discord API error: {error}")
        return JsonResponse({"error": "Discord API error"}, status=500)
    
    def get_post_data(self, request: HttpRequest) -> dict:
        """Get POST data as dictionary."""
        return request.POST.dict()
    
    def get_json_data(self, request: HttpRequest) -> dict:
        """Get JSON data from request body."""
        import json
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return {}
