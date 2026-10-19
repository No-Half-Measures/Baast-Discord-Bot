from datetime import datetime, timedelta
import pytz
import asyncio
import logging
import sys

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from channels.layers import get_channel_layer

from hikari import NotFoundError, RESTApp, UnauthorizedError, GuildTextChannel, Embed, Color

from app.models import Events, Config, Attendance


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')
AUTH_URL = getattr(settings, 'AUTH_URL')
REDIRECT_URL = getattr(settings, 'REDIRECT_URL')


class Announcer(View):
    template_name = 'discord/admin/dash_admin_announcer.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        access_token = await sync_to_async(request.session.get)("access_token")
        if not access_token: #if token is valid
            return redirect("/login")
        
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as client:
            try:
                user: DUser = await sync_to_async(DUser)(await client.fetch_my_user(), request.user)
            except UnauthorizedError:
                return redirect(reverse('discord:dash_home'))

            if not user.is_staff:
                return redirect(reverse('discord:dash_home'))
        await restapp.close()

        return await sync_to_async(render)(request, self.template_name, context={
            "user" : user,
            "guilds" : guilds,
        })


    @classonlymethod
    def getTotalResponceCnt(cls, events: list[Events]) -> int:
        att: list[Attendance] = []
        for event in events:
            try:
                a = Attendance.objects.get(id=event.id)
            except Attendance.DoesNotExist:
                continue
            else:
                if a:
                    att.append(a)
            
        responce_cnt = 0
        for a in att:
            responce_cnt += len(a.attending) + len(a.declined) + len(a.tentative)

        return responce_cnt
    

    async def post(self, request: HttpRequest, *args, **kwargs):
        access_token = await sync_to_async(request.session.get)("access_token")
        if not access_token: #if token is valid
            return JsonResponse({"error": "Not Logged In"}, status=400)

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if is_ajax:
            if request.method == "POST":
                # Get Data and break it down
                data = request.POST.dict()
          
                title: str = data['title']
                description: str = data['desc']
                img = data['img'] #imgs?//attachments?
                push_to_logs: bool = data['push_to_logs']
                is_test: bool = bool(data['is_test'])
                push_to_news: bool = data['push_to_news']
                
                
                uploaded_file = request.FILES['files']
                
                print(uploaded_file)
                restapp = RESTApp()
                await restapp.start()
                
                user: DUser = None
                async with restapp.acquire(access_token, "BEARER") as bearer:
                    try:
                        user = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
                    except UnauthorizedError or NotFoundError:
                        await restapp.close()
                        return redirect(reverse('discord:dash_home'))
                    
                await restapp.close()
                
                
                channel_layer = get_channel_layer()
                await channel_layer.send('discord', {'type': 'post.announcement', 
                                                    'title': title,
                                                    'description': description,
                                                    'admin_id': int(user.id),
                                                    'is_test': is_test,
                                                    'push_to_news': push_to_news,
                                                    'push_to_logs': push_to_logs
                                                    })
                
                return JsonResponse({"success": "Win"}, status=200)
        return JsonResponse({"error": "Error"}, status=400)
