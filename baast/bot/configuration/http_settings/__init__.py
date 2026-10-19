import logging
import os
import sys

from loguru import logger

from baast.settings import *

INSTALLED_APPS = [
    *INSTALLED_APPS,
    'django_prometheus',
    #"django_discord.py.plugins",
    #"django_discord.py.example_bot",
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'discord.public_middleware.PublicEndpointMiddleware',  # Add this before auth middleware
    *MIDDLEWARE,
    
    'discord.middleware.GuildMiddleware',
    'discord.middleware.GuildAccessMiddleware',

    'discord.middleware.PrometheusHostMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')


# from split_settings.tools import include, optional
# include(
#     "../common_components/base.py",
#     "../common_components/channels.py",
#     "../common_components/django_extensions.py",
#     optional(
#         os.getenv(
#             "DJANGO_DISCORD_PY_SERVER_LOCAL_SETTINGS",
#             "components/local_settings.py",
#         ),
#     ),
# )