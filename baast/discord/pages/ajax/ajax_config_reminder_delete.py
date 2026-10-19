import logging

from asgiref.sync import sync_to_async

from django.http import HttpRequest
from django.shortcuts import redirect
from django.http import JsonResponse

from discord.pages.ajax.base import BaseAjaxView

from app.models import Events


from loguru import logger


class AjaxConfigReminderDelete(BaseAjaxView):
    async def post(self, request: HttpRequest, *args, **kwargs):
        # access_token is automatically provided by base class
        access_token = kwargs.get('access_token')
        guild_hash = kwargs['hashguild']
        
        # Get guild configuration using base class method
        config, error_response = await self.get_guild_config(guild_hash)
        if error_response:
            return error_response

        if not config.is_premium:
                return JsonResponse({'error': 'Not a premium guild'}, status=400)
                
        try:
            index = int(request.POST.get('index'))

            # Validate index
            if 0 <= index < len(config.reminders):
                try:
                    events = await sync_to_async(list)(Events.objects.filter(gid=config))
                    for event in events:
                        if len(event.sentReminders) > index:
                            event.sentReminders.pop(index)
                            await event.asave()
                except Exception as e:
                    logger.error(f'Error updating events reminders array: {str(e)}')
                
                # Remove the reminder at the specified index
                config.reminders.pop(index)
                await config.asave()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Invalid reminder index'}, status=400)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxConfigReminderDelete: {e}")
            return redirect('/login/')
