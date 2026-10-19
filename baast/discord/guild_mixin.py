"""
GuildMixin - Comprehensive mixin for panel views that require guild validation.
Combines Discord authentication and guild-specific functionality.
"""

import logging
from typing import Optional, Tuple, Any
from asgiref.sync import sync_to_async
from django.http import JsonResponse, HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

from .hashids import Hashids
from .mixins import DiscordAuthMixin
from app.models import Config

from loguru import logger


SALT = getattr(settings, 'HASH_SALT', None)


class GuildMixin(DiscordAuthMixin):
    """
    Comprehensive mixin for panel views that require guild validation.
    
    Usage:
        class MyPanelView(GuildMixin, View):
            async def get(self, request, *args, **kwargs):
                # Validate session and get guild data
                guild_data, error_response = await self.validate_guild_request(request, kwargs)
                if error_response:
                    return error_response
                
                # Use guild_data.guild_id, guild_data.config, etc.
                pass
    """
    
    async def validate_guild_request(self, request: HttpRequest, kwargs: dict) -> Tuple[Optional['GuildData'], Optional[JsonResponse]]:
        """
        Validate the entire guild request including session and guild access.
        
        Args:
            request: Django HttpRequest
            kwargs: URL kwargs containing 'hashguild'
            
        Returns:
            Tuple of (GuildData, error_response)
            - GuildData: Contains guild_id, config, and other guild info
            - error_response: JsonResponse if validation failed, None if success
        """
        # Step 1: Validate Discord session
        access_token, error_response = await self.validate_session(request)
        if error_response:
            return None, error_response
        
        # Step 2: Extract and validate guild hash
        guild_hash = kwargs.get('hashguild')
        if not guild_hash:
            logger.warning("No guild hash provided in URL")
            return None, JsonResponse({"error": "Guild ID required"}, status=400)
        
        # Step 3: Decode guild hash
        try:
            hashids = Hashids(salt=SALT)
            guild_id = hashids.decode(guild_hash)[0]
        except Exception as e:
            logger.warning(f"Invalid guild hash {guild_hash}: {e}")
            return None, redirect(reverse('discord:dash_home'))
        
        # Step 4: Fetch guild configuration
        try:
            config = await sync_to_async(Config.objects.get)(guild=guild_id)
        except Config.DoesNotExist:
            logger.warning(f"Config not found for guild {guild_id}")
            return None, redirect(reverse('discord:dash_home'))
        except Exception as e:
            logger.error(f"Error fetching config for guild {guild_id}: {e}")
            return None, JsonResponse({"error": "Failed to load guild configuration"}, status=500)
        
        # Step 5: Create GuildData object
        guild_data = GuildData(
            guild_id=guild_id,
            guild_hash=guild_hash,
            config=config,
            access_token=access_token
        )
        
        return guild_data, None
    
    async def get_guild_config(self, guild_id: int) -> Tuple[Optional[Config], Optional[JsonResponse]]:
        """
        Get guild configuration by guild ID.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Tuple of (config, error_response)
        """
        try:
            config = await sync_to_async(Config.objects.get)(guild=guild_id)
            return config, None
        except Config.DoesNotExist:
            logger.warning(f"Config not found for guild {guild_id}")
            return None, JsonResponse({"error": "Guild not found"}, status=404)
        except Exception as e:
            logger.error(f"Error fetching config for guild {guild_id}: {e}")
            return None, JsonResponse({"error": "Failed to load guild configuration"}, status=500)
    
    async def decode_guild_hash(self, guild_hash: str) -> Tuple[Optional[int], Optional[JsonResponse]]:
        """
        Decode guild hash to guild ID.
        
        Args:
            guild_hash: Hashed guild ID from URL
            
        Returns:
            Tuple of (guild_id, error_response)
        """
        try:
            hashids = Hashids(salt=SALT)
            guild_id = hashids.decode(guild_hash)[0]
            return guild_id, None
        except Exception as e:
            logger.warning(f"Invalid guild hash {guild_hash}: {e}")
            return None, redirect(reverse('discord:dash_home'))
    
    async def validate_guild_access(self, request: HttpRequest, guild_id: int) -> Tuple[bool, Optional[JsonResponse]]:
        """
        Validate that the user has access to the guild.
        This can be extended to check permissions, roles, etc.
        
        Args:
            request: Django HttpRequest
            guild_id: Discord guild ID
            
        Returns:
            Tuple of (has_access, error_response)
        """
        # For now, just return True - this can be extended with actual permission checks
        # You could integrate with your existing guild access middleware logic here
        return True, None


class GuildData:
    """
    Data class containing guild-related information.
    """
    
    def __init__(self, guild_id: int, guild_hash: str, config: Config, access_token: str):
        self.guild_id = guild_id
        self.guild_hash = guild_hash
        self.config = config
        self.access_token = access_token
    
    def __repr__(self):
        return f"GuildData(guild_id={self.guild_id}, guild_hash={self.guild_hash})"


# Convenience function for views that don't need the full mixin
async def get_guild_data(request: HttpRequest, kwargs: dict) -> Tuple[Optional[GuildData], Optional[JsonResponse]]:
    """
    Standalone function to get guild data without using the mixin.
    Useful for views that can't inherit from GuildMixin.
    """
    # Create a temporary mixin instance
    mixin = GuildMixin()
    return await mixin.validate_guild_request(request, kwargs)
