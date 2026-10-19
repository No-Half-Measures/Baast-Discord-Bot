import logging

from asgiref.sync import sync_to_async

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from hikari import OwnUser

from discord.pages.ajax.base import BaseAjaxView

from app.models import Option_Presets, Preset_Roles


from loguru import logger

class AjaxPresetRolesDelete(BaseAjaxView):
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
            restapp = await self.get_restapp(access_token)
            try:
                async with restapp.acquire(access_token, "BEARER") as bearer:
                    author: OwnUser = await bearer.fetch_my_user()
            finally:
                await self.release_restapp(access_token, restapp)
                
            preset_id = int(kwargs['preset'])
            roleset_id = int(kwargs['roleset'])
            
            try:
                option: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=preset_id)
            except Option_Presets.DoesNotExist:
                return redirect(reverse('discord:dash_home'))
            
            
            try:
                preset_roles: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id=roleset_id, gid=config, preset=option)
            except Preset_Roles.DoesNotExist:
                return JsonResponse({"error": "Error"}, status=400)
            
            await preset_roles.adelete()
            
            return JsonResponse({ "status": "success"}, status=200)
        except Exception as e:
            from loguru import logger
            logger.error(f"Error in AjaxPresetRolesDelete: {e}")
            return redirect('/login/')
