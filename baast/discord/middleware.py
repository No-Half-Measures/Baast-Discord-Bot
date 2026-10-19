import sys
from asgiref.sync import sync_to_async, async_to_sync

from django.conf import settings
from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from hikari import RESTApp, UnauthorizedError, NotFoundError

from discord.OAuth2 import DUser, convertGuilds
from discord.hashids import Hashids

from loguru import logger


SALT = getattr(settings, 'HASH_SALT', None)

class GuildMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        # Extract data from the URL path
        url_path = request.path
        parts = url_path.strip('/').split('/')
        
        if request.path.startswith('/panel/') and len(parts) > 1 and parts[1] not in ['ajax', 'admin', 'none', 'user', 'metrics', 'health', 'pool-status']:
            request.site_section = 'panel'
            guild_hash = parts[1]
            
            # Add custom data to the request object
            request.guild_data = {
                'hash': guild_hash,
            }
        elif request.path.startswith('/panel/') and len(parts) == 1:
            request.site_section = 'panel_home'
        elif request.path.startswith('/panel/') and len(parts) > 1 and parts[1] == 'user':
            request.site_section = 'panel_user'
        else:
            request.site_section = 'default'
        
        response = self.get_response(request)
        return response
    
class GuildAccessMiddleware(MiddlewareMixin):
    def __call__(self, request):
        # Load navigation data for panel pages
        if (getattr(request, 'site_section', '') == 'panel_home' or 
            getattr(request, 'site_section', '') == 'panel' or 
            getattr(request, 'site_section', '') == 'panel_user'):
            try:
                guilds, user = async_to_sync(self.get_guilds)(request)
                request.nav_guilds = guilds
                request.nav_user = user
            except Exception as e:
                from loguru import logger
                logger.error(f"Error getting guilds in middleware: {e}")
                request.nav_guilds = None
                request.nav_user = None
            
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        session_key = request.session.session_key
        
        if session_key:
            url_path = request.path
            parts = url_path.strip('/').split('/')
            
            if request.path.startswith('/panel/') and len(parts) > 1 and parts[1] not in ['ajax', 'admin', 'none', 'metrics', 'health', 'pool-status']:
                guild_hash = parts[1]
                hashids = Hashids(salt=SALT)
                guild_id = hashids.decode(guild_hash)[0]
                
                user_id = request.session.get("_auth_user_id")
                
                response_channel_name = guild_hash + "_" + user_id + "_response"
                
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.send)('discord', {'type': 'is.event.manager', 'response_channel': response_channel_name, 'guild_id': guild_id, 'user_id': user_id, 'section': 'event'})
                response = async_to_sync(channel_layer.receive)(response_channel_name)

                if not response['has_access']:
                    return redirect(reverse('Discord-Login'))
        return None
    
    async def get_guilds(self, request: HttpRequest):
        user_id = await sync_to_async(request.session.get)("_auth_user_id")
        access_token = await sync_to_async(request.session.get)("access_token")
        
        if not access_token:
            return None, None
        
        guilds, user = None, None
        
        # Use connection pool instead of creating new RESTApp
        from .connection_pool import get_connection_pool
        pool = get_connection_pool()
        
        try:
            restapp, _ = await pool.get_client(access_token)
            is_temporary = access_token not in pool._pool
            
            async with restapp.acquire(access_token, "BEARER") as bearer:
                try:
                    guilds = await convertGuilds(bearer.fetch_my_guilds(), user_id)
                    user = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
                except (UnauthorizedError, NotFoundError) as e:
                    logger.error(f"Discord API error in middleware: {e}")
                    await pool.release_client(access_token, restapp, is_temporary)
                    return None, None
                except Exception as e:
                    logger.error(f"Unexpected error in middleware: {e}")
                    await pool.release_client(access_token, restapp, is_temporary)
                    return None, None
            
            # Release connection back to pool
            await pool.release_client(access_token, restapp, is_temporary)
            
        except Exception as e:
            logger.error(f"Connection pool error: {e}")
            return None, None
            
        return guilds, user

class PrometheusHostMiddleware:
    """
    Middleware to handle Prometheus requests with invalid host headers.
    This allows Prometheus to scrape Django metrics without host validation issues.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is a Prometheus metrics request from internal network
        if (request.path == '/metrics' and 
            request.META.get('HTTP_HOST', '').startswith('baast-web:')):
            # Modify the host header to be valid for Django
            request.META['HTTP_HOST'] = 'baast-web'
            # Also update SERVER_NAME if it exists
            if 'SERVER_NAME' in request.META:
                request.META['SERVER_NAME'] = 'baast-web'
        
        response = self.get_response(request)
        return response