import pytz
import logging

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles

from cache.models import DiscordChannel


from loguru import logger


class ConfigView(GuildMixin, View):
    template_name = 'discord/dash_config.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return async_to_sync(view)

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        guild_data, error_response = await self.validate_guild_request(request, kwargs)
        if error_response:
            return error_response

        channels: list[DiscordChannel] = await Channels.get(guild_data.guild_id)
        roles = await Roles.get(guild_data.guild_id)
        
        return await sync_to_async(render)(request, self.template_name, context={
          "channels": channels,
          "roles": roles,
          "timezones" : pytz.all_timezones,
        })