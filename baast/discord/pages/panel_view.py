from datetime import datetime, timedelta
import pytz
import asyncio
import logging
import sys

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render, redirect
from django.shortcuts import render
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from hikari import RESTApp, UnauthorizedError, User

from discord.hashids import Hashids
from discord.OAuth2 import DUser, convertGuilds

import os
from django.http import HttpResponse
from prometheus_client import CollectorRegistry, multiprocess, generate_latest
from prometheus_client import REGISTRY, CONTENT_TYPE_LATEST


from loguru import logger


class PanelView(View):
    template_name = 'discord/dash_home.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    @sync_to_async
    @method_decorator(login_required(login_url='/login/'))
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        return render(request, self.template_name)
