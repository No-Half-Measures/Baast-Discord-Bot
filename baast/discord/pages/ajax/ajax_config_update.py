import logging
import json

from django.http import HttpRequest
from django.shortcuts import redirect
from django.http import JsonResponse
from django.core.cache.backends.base import DEFAULT_TIMEOUT

from discord.pages.ajax.base import BaseAjaxView

from bot.bot.utils.util import DBifyReminder


from loguru import logger


class AjaxConfigUpdate(BaseAjaxView):
    async def post(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response
        
                
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body)
            
            # Update settings
            config.signup_overflow_method = int(data.get('signup_overflow_method', 0))
            config.thread_delete_method = int(data.get('thread_delete_method', 0))
            
            # Update autoclean settings if provided
            if config.is_premium:
                autoclean = data.get('autoclean', [0, 0, 0])
                if isinstance(autoclean, list) and len(autoclean) == 3:
                    config.autoclean_t = DBifyReminder(autoclean)
            
            # Save the changes
            await config.asave()
            
            return JsonResponse({'success': True})
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxConfigUpdate: {e}")
            return redirect('/login/')
