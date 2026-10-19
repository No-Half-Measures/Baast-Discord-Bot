from datetime import datetime, timedelta
import pytz
import asyncio
import logging

from asgiref.sync import sync_to_async, async_to_sync

import plotly.graph_objects as go

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

from discord.guild_mixin import GuildMixin
from discord.pages.methods.channels import Channels
from discord.pages.methods.roles import Roles
from discord.hashids import Hashids

from app.models import Events, Config, Attendance, Option_Presets, Templates, Stats_Created, Stats_Deleted, Stats_Edited, Stats_Responded


from loguru import logger


class OverView(GuildMixin, View):
    template_name = 'discord/dash_overview.html'

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
        
        now = datetime.now()
        try:
            upcoming_events = await sync_to_async(list)(Events.objects.filter(gid=guild_data.config, event_date__gte=now).order_by('event_date')[:5])
        except Exception as e:
            logger.error(f"Error fetching upcoming events: {e}")
            upcoming_events = []
        
        try:
            events = await sync_to_async(list)(Events.objects.filter(gid=guild_data.config))
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            events = []
        
        try:
            responce_cnt = await sync_to_async(OverView.getTotalResponceCnt)(events)
        except Exception as e:
            logger.error(f"Error fetching responce count: {e}")
            responce_cnt = 0
        
        try:
            preset_cnt = await sync_to_async(Option_Presets.objects.filter(gid=guild_data.config).count)()
        except Exception as e:
            logger.error(f"Error fetching preset count: {e}")
            preset_cnt = 0
        
        try:
            template_cnt = await sync_to_async(Templates.objects.filter(gid=guild_data.config).count)()
        except Exception as e:
            logger.error(f"Error fetching template count: {e}")
            template_cnt = 0
        
        try:
            event_stats = await sync_to_async(self.buildEventStats)(guild_data.config, months=12)
        except Exception as e:
            logger.error(f"Error building event stats: {e}")
            event_stats = None
        
        try:
            responce_stats = await sync_to_async(self.buildResponceStats)(guild_data.config, days=30)
        except Exception as e:
            logger.error(f"Error building responce stats: {e}")
            responce_stats = None

        return await sync_to_async(render)(request, self.template_name, context={
            "events" : upcoming_events,
            
            "channels": channels,
            "roles": roles,
            "events_cnt" : len(events),
            "responce_cnt" : responce_cnt,
            "preset_cnt" : preset_cnt,
            "template_cnt" : template_cnt,
            "timezones" : pytz.all_timezones,
            
            "event_stats": event_stats,
            "responce_stats": responce_stats,
        })
    

    @classonlymethod
    def getTotalResponceCnt(cls, events: list[Events]) -> int:
        att: list[Attendance] = []
        for event in events:
            try:
                attendance = event.GetAttendance()
                # preset = event.GetOptionPreset()
            except Attendance.DoesNotExist:
                continue
            # except Option_Presets.DoesNotExist:
            #     continue
            else:
                if attendance:
                    att.append(attendance)
            
        responce_cnt = 0
        for a in att:
            responce_cnt += (len(a.option_1) + len(a.option_2) + len(a.option_3) + len(a.option_4) + len(a.option_5) + 
                             len(a.option_6) + len(a.option_7) + len(a.option_8) + len(a.option_9))

        return responce_cnt
    
    def buildEventStats(self, config:Config, months:int = 3):
        # Use timezone-aware datetime consistently
        now = tz.now()
        d = now - tz.timedelta(days=(30 * months))
        
        cStats: list[Stats_Created] = Stats_Created.objects.filter(gid=config.id, date__gte=d)
        eStats: list[Stats_Edited]  = Stats_Edited.objects.filter(gid=config.id, date__gte=d)
        dStats: list[Stats_Deleted]  = Stats_Deleted.objects.filter(gid=config.id, date__gte=d)
        
        created_cnt: list[int] = [0] * months
        edited_cnt: list[int] = [0] * months
        deleted_cnt: list[int] = [0] * months

        dates: list[str] = [None] * months

        # Generate date labels (most recent first)
        for idx in range(months):
            pd = now - tz.timedelta(days=(30 * idx))
            dates[idx] = pd.strftime('%m/%Y')
        
        # Process stats by directly checking which month they belong to
        for stat in cStats:
            stat_date = stat.date
            for idx in range(months):
                # Calculate the target month date
                target_date = now - tz.timedelta(days=(30 * idx))
                # Check if stat belongs to this month
                if (stat_date.month == target_date.month and 
                    stat_date.year == target_date.year):
                    created_cnt[idx] += 1
                    break
            
        for stat in eStats:
            stat_date = stat.date
            for idx in range(months):
                # Calculate the target month date
                target_date = now - tz.timedelta(days=(30 * idx))
                # Check if stat belongs to this month
                if (stat_date.month == target_date.month and 
                    stat_date.year == target_date.year):
                    edited_cnt[idx] += 1
                    break
            
        for stat in dStats:
            stat_date = stat.date
            for idx in range(months):
                # Calculate the target month date
                target_date = now - tz.timedelta(days=(30 * idx))
                # Check if stat belongs to this month
                if (stat_date.month == target_date.month and 
                    stat_date.year == target_date.year):
                    deleted_cnt[idx] += 1
                    break

        f1 = go.Figure(
            data = [
                go.Scatter(x=dates, y=deleted_cnt, name="Deleted", mode='lines+markers', line_color='#202535'),
                go.Scatter(x=dates, y=edited_cnt, name="Edited", mode='lines+markers', line_color='#f39c12'),
                go.Scatter(x=dates, y=created_cnt, name="Created", mode='lines+markers', line_color='#edbe49'),
            ],
            layout = {"xaxis": {"title": "Date", 'autorange': 'reversed'}, "yaxis": {"title": "Count"}}
        )
        
        return f1.to_html(include_plotlyjs='cdn', include_mathjax='cdn', full_html = False, config= {'displaylogo': False})

    def buildResponceStats(self, config:Config, days:int = 30):
        d = tz.now() - tz.timedelta(days=days)
        
        rStats: list[Stats_Responded] = Stats_Responded.objects.filter(gid=config.id, date__gte=d)
        
        max_hours = 0
        for stat in rStats:
            max_hours = max(max_hours, stat.hours_after)
        
        responce_hours: list[int] = [0] * (max_hours + 1)
        hours = list(range(len(responce_hours)))
        
        for stat in rStats:
            responce_hours[stat.hours_after] += 1
        
        f1 = go.Figure(
            data=[
                go.Bar(x=hours, y=responce_hours, name="Responses", marker_color='#edbe49')
            ],
            layout={
                "xaxis": {"title": "Hours After Event Announcement"},
                "yaxis": {"title": "Number of First Responses"},
                "title": "Distribution of First Response Times"
            }
        )
        
        return f1.to_html(include_plotlyjs='cdn', include_mathjax='cdn', full_html = False, config= {'displaylogo': False})
    
