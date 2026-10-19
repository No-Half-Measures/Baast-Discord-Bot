
import asyncio
from typing import Optional, Tuple, Any
from asgiref.sync import sync_to_async
from django.http import JsonResponse
from hikari import RESTApp, TokenType

from .connection_pool import get_connection_pool

class DiscordAuthMixin:
    """
    Mixin providing Discord authentication and connection management.
    Integrates with the connection pool for better performance.
    """
    
    async def get_access_token(self, request) -> Optional[str]:
        """Get access token from session."""
        return await sync_to_async(request.session.get)("access_token")
    
    async def validate_session(self, request) -> Tuple[Optional[str], Optional[JsonResponse]]:
        """
        Validate user session and return access token.
        Returns: (access_token, error_response)
        """
        access_token = await self.get_access_token(request)
        if not access_token:
            return None, JsonResponse({"error": "Not Logged In"}, status=400)
        return access_token, None
    
    async def get_discord_client(self, access_token: str) -> Tuple[RESTApp, Any]:
        """
        Get Discord client using connection pool.
        Returns: (restapp, client_context_manager)
        """
        pool = get_connection_pool()
        restapp, client_context = await pool.get_client(access_token)
        return restapp, client_context
    
    async def release_discord_client(self, access_token: str, restapp: RESTApp, is_temporary: bool = False):
        """Release Discord client back to pool."""
        pool = get_connection_pool()
        await pool.release_client(access_token, restapp, is_temporary)
    
    async def get_restapp(self, access_token: str) -> RESTApp:
        """
        Get a RESTApp instance from the connection pool.
        The caller is responsible for managing the connection lifecycle.
        
        Usage:
            restapp = await self.get_restapp(access_token)
            async with restapp.acquire(access_token, TokenType.BEARER) as bearer:
                # Use bearer here
                pass
            await self.release_restapp(access_token, restapp)
        """
        pool = get_connection_pool()
        restapp, _ = await pool.get_client(access_token)
        return restapp
    
    async def release_restapp(self, access_token: str, restapp: RESTApp):
        """Release a RESTApp back to the connection pool."""
        pool = get_connection_pool()
        is_temporary = access_token not in pool._pool
        await pool.release_client(access_token, restapp, is_temporary)