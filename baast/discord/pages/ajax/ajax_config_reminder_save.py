import logging
import json

from asgiref.sync import sync_to_async

from django.http import HttpRequest
from django.shortcuts import redirect
from django.http import JsonResponse

from discord.pages.ajax.base import BaseAjaxView

from app.models import Events


from loguru import logger


class AjaxConfigReminderSave(BaseAjaxView):
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
            index = request.POST.get('index')
            reminder_data = json.loads(request.POST.get('reminder_data'))
            
            # Validate data
            if not reminder_data.get('name') or not reminder_data.get('message'):
                return JsonResponse({'error': 'Missing required fields'}, status=400)
            
            # If reminder is valid, update or add it
            if index == '-1':
                # New reminder
                config.reminders.append(reminder_data)
            else:
                # Update existing reminder
                index = int(index)
                if 0 <= index < len(config.reminders):
                    config.reminders[index] = reminder_data
                else:
                    logger.warning(f'Guild {config.guild} has {len(config.reminders)} reminders but index is {index}.')
                    return JsonResponse({'error': 'Invalid reminder index'}, status=400)
            
            await config.asave()
            
            events = await sync_to_async(list)(Events.objects.filter(gid=config))
            for event in events:
                event.sentReminders = [False] * len(config.reminders)
                await sync_to_async(event.save)()
            
            return JsonResponse({'success': True})
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxConfigReminderDelete: {e}")
            return redirect('/login/')
