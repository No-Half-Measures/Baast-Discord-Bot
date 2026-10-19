from datetime import datetime, timedelta
import pytz
import asyncio
import logging

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone as tz

from hikari import RESTApp, UnauthorizedError, NotFoundError

import plotly.express as px
import plotly.graph_objects as go

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles
from discord.hashids import Hashids

from app.models import Events, Config, Stats_Created, Stats_Deleted, Stats_Edited


from loguru import logger


class StatsView(GuildMixin, View):
    template_name = 'discord/dash_stats.html'

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
        
        channels = await Channels.get(guild_data.guild_id)
        roles = await Roles.get(guild_data.guild_id)

        thirtydaystats = await sync_to_async(self.buildGeneralStats)(guild_data.config)

        return await sync_to_async(render)(request, self.template_name, context={
            "channels": channels,
            "roles": roles,
            "30daystats": thirtydaystats,
            "timezones" : pytz.all_timezones,
        })

    def buildGeneralStats(self, config:Config, days:int = 30):
        d = tz.now() - tz.timedelta(days=days)

        cStats: list[Stats_Created] = Stats_Created.objects.filter(gid=config.id, date__gte=d)
        eStats: list[Stats_Edited]  = Stats_Edited.objects.filter(gid=config.id, date__gte=d)
        dStats: list[Stats_Deleted]  = Stats_Deleted.objects.filter(gid=config.id, date__gte=d)

        created_cnt: list[int] = [0] * days
        edited_cnt: list[int] = [0] * days
        deleted_cnt: list[int] = [0] * days

        dates: list[str] = [None] * days
        #dates: list[int] = [0] * days


        idx = 0
        while idx != days:
            pd = datetime.now() - timedelta(idx)

            dates[idx] = datetime.strftime(pd, '%d/%m')
            idx += 1
        
        for stat in cStats:
            idx = 0
            while idx != days:
                if stat.isXDate(idx):
                    created_cnt[idx]+=1
                idx += 1
            
        for stat in eStats:
            idx = 0
            while idx != days:
                if stat.isXDate(idx):
                    edited_cnt[idx]+=1
                idx += 1
            
        for stat in dStats:
            idx = 0
            while idx != days:
                if stat.isXDate(idx):
                    deleted_cnt[idx]+=1
                idx += 1
            

        f1 = go.Figure(
            data = [
                go.Scatter(x=dates, y=deleted_cnt, name="Deleted", mode='lines+markers', line_color='#202535'),
                go.Scatter(x=dates, y=edited_cnt, name="Edited", mode='lines+markers', line_color='#f39c12'),
                go.Scatter(x=dates, y=created_cnt, name="Created", mode='lines+markers', line_color='#edbe49'),
            ],
            layout = {"xaxis": {"title": "Date", 'autorange': 'reversed'}, "yaxis": {"title": "Count"}}
        )
        
        return f1.to_html(include_plotlyjs='cdn', include_mathjax='cdn', full_html = False, config= {'displaylogo': False})

