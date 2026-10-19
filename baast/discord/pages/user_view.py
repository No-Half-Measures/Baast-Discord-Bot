from datetime import datetime, timedelta
import pytz
import asyncio
import logging
import sys

import stripe

from asgiref.sync import sync_to_async, async_to_sync

from django.http import HttpRequest
from django.shortcuts import render, redirect
from django.utils.decorators import classonlymethod
from django.views.generic import View
from django.core.cache import cache
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from hikari import RESTApp, UnauthorizedError

from discord.mixins import DiscordAuthMixin


from loguru import logger

CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')
AUTH_URL = getattr(settings, 'AUTH_URL')
REDIRECT_URL = getattr(settings, 'REDIRECT_URL')


class UserView(View, DiscordAuthMixin):
    template_name = 'discord/dash_user.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        # Use the mixin's session validation
        access_token, error_response = await self.validate_session(request)
        if error_response:
            return error_response
                
        data = {}
        if user.stripeCustomerId != None:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            try:
                subscriptions = stripe.Subscription.list(customer=user.stripeCustomerId)
                data['subscriptions'] = [sub.id for sub in subscriptions]
            except:
                data['subscriptions'] = None
        
        data['timezones'] = pytz.all_timezones

        return await sync_to_async(render)(request, self.template_name, context=data)
