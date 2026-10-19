import os
import importlib
import uvicorn

import django

from channels.routing import ProtocolTypeRouter, ChannelNameRouter
from django.core.asgi import get_asgi_application

from bot.consumers import DiscordConsumer

# os.environ.setdefault("INSTALLED_APPS", "baast.settings")
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baast.settings")
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baast.configuration.http_settings")
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baast.configuration.worker_settings")
#django.setup()

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import after django is setup so we can count on settings being initialized
consumers_module = importlib.import_module('bot.consumers')


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        #"discord": DiscordConsumer
        "channel": ChannelNameRouter(
            {
                "discord": DiscordConsumer.as_asgi(),
            }
        ),
    }
)
