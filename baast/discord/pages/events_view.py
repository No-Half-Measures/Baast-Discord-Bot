import sys
from datetime import datetime, timedelta
import arrow
import asyncio
import logging
import time as Time
import dateutil.parser

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, redirect
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse

from gspread import Worksheet

from hikari import RESTApp, UnauthorizedError, OwnUser, NotFoundError

from channels.layers import get_channel_layer
import pytz

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles
from discord.hashids import Hashids

from cache.helpers import GetUser
from cache.models import DiscordChannel, DiscordUser

from app.models import Events, Events_Links, Config, Attendance, Attendance_Linked, Templates, Option_Presets , Stats_Created, Stats_Edited

from bot.bot.utils.enums import SignupOption

from loguru import logger


class EventsView(GuildMixin, View):
    template_name = 'discord/dash_events.html'

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
        
        events: Events = await sync_to_async(Events.objects.filter)(gid=guild_data.config)
        events = await sync_to_async(events.order_by)('event_date')
        
        events_linked: Events_Links = await sync_to_async(Events_Links.objects.filter)(linked_guild=guild_data.config)
        
        channels: list[DiscordChannel] = await Channels.get(guild_data.guild_id)
        roles = await Roles.get(guild_data.guild_id)
        
        context ={
            "events": events,
            "linked_events": events_linked,
            
            "channels": channels,
            "roles": roles,
            "timezones" : pytz.all_timezones,
        }
        
        return await sync_to_async(render)(request, self.template_name, context)