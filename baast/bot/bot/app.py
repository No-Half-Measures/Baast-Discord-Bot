import datetime
import logging

from loguru import logger

from bot.signals import bot_ready
from bot.bot.utils.mod_log import ModLogValues

from app.models import Config, Templates, Option_Presets

import hikari
from hikari import Intents, events

from django.conf import settings
from asgiref.sync import sync_to_async

class Baast(hikari.GatewayBot):
    __slots__ = (
        "_dynamic",
        "version",
        "presence",
        "ready"
    )
    
    async def to_discord(self, message):
        if message.record["level"].name == "INFO":
            embed = hikari.Embed(
                color=ModLogValues.get_color(ModLogValues.event), 
                description=f'{message.record["message"]} **@** <t:{int(datetime.datetime.now(datetime.UTC).timestamp())}:R>'
            )
            #await self.rest.create_message(1211801612910329886, embed)
        else:
            embed = hikari.Embed(
                color=ModLogValues.get_color(int((message.record["level"].no - 20) / 10)), 
                description=f'{message.record["message"]} **@** <t:{int(datetime.datetime.now(datetime.UTC).timestamp())}:R>'
            )
            #await self.rest.create_message(1211801465752920155, embed)


    def __init__(self, version: str) -> None:
        self._dynamic = "./baast/data/dynamic"
        self.version = version
        self.ready = False
        #self.cache = {}
        
        logger.add(self.to_discord, level="INFO")

        super().__init__(
            token=getattr(settings, 'CLIENT_TOKEN'),
            intents=Intents.GUILD_MESSAGES | Intents.GUILD_INTEGRATIONS | Intents.GUILDS | Intents.GUILD_MEMBERS,
            banner=None,
        )
        
        subscriptions = {
            events.StartingEvent: self.on_starting,
            events.StartedEvent: self.on_started,
            #events.StoppingEvent: self.on_stopping,
            #events.GuildLeaveEvent: self.on_guild_leave,
            #events.GuildMessageCreateEvent: self.on_guild_message_create,
            #lightbulb.CommandErrorEvent: self.on_command_error,
        }
        
        for e, c in subscriptions.items():
            self.event_manager.subscribe(e, c)
    
    # enter the async context manager
    async def __aenter__(self):
        # report a message
        print('>entering the context manager')
 
    # exit the async context manager
    async def __aexit__(self, exc_type, exc, tb):
        # report a message
        print('>exiting the context manager')

    async def on_starting(self, _: events.StartingEvent) -> None:
        logger.info('Baast Starting')
        
        #await self.setup_templates()
        #await self.setup_options()
        return

    async def on_started(self, _: events.StartedEvent) -> None:
        logger.info('Baast Started')
        
        bot_ready.send_robust(sender=self.__class__, bot=self)
        
        self.ready = True
        
        #avatarFile = open("./baast/data/baast_dev.png", 'rb')
        #await self.rest.edit_my_user(avatar=hikari.Bytes(avatarFile, "baast_dev.png"))
        

    async def on_stopping(self, _: events.StoppingEvent) -> None:
        logger.info('Baast Stopped')

    @property
    def me(self) -> hikari.User:
        if self._me:
            return self._me
        if not (user := self.cache.get_me()):
            raise RuntimeError("Own user can't be accessed from cache")
        return user

    async def setup_templates(self):
        baastCnf = await sync_to_async(Config.objects.get)(guild=MAIN_GUILD_ID)
        
        template, _ = await sync_to_async(Templates.objects.update_or_create)(
            gid = baastCnf,
            name = 'Default',
            defaults = {
                "sheetid": '1vF3d0ZHPfHUaW8sdl56gkdm4H8la7QS80DCVLz3kC14',
                "worksheetid": 1638393836,
                "cells": {
                            "1": {
                                "Declined": "B7",
                                "Attending": "A7",
                                "Tentative": "C7"
                            },
                            "cell_date": "j2",
                            "cell_desc": "e3",
                            "cell_link": "n2",
                            "cell_title": "a1"
                        },
                "lnkd_opt_presets": [1],
            }
        )
        
        template, _ = await sync_to_async(Templates.objects.update_or_create)(
            gid = baastCnf,
            name = 'Squad',
            defaults = {
                "sheetid": '1vF3d0ZHPfHUaW8sdl56gkdm4H8la7QS80DCVLz3kC14',
                "worksheetid": 0,
                "cells": {
                            "1": {
                                "Declined": "B7",
                                "Attending": "A7",
                                "Tentative": "None"
                            },
                            "3": {
                                "MG": "A7",
                                "HAT": "A7",
                                "LAT": "A7",
                                "Medic": "A7",
                                "Rifleman": "A7",
                                "Squad Lead": "A7"
                            },
                            "cell_date": "i2",
                            "cell_desc": "d3",
                            "cell_link": "m2",
                            "cell_title": "a1"
                        },
                "lnkd_opt_presets": [1, 3],
                "thumb_url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/393380/eb66a8cb52165274c84cae6526205065d13119d5.jpg",
                "emoji": "<:squad:1393621868480561264>"
            },
        )
        
        template, _ = await sync_to_async(Templates.objects.update_or_create)(
            gid = baastCnf,
            name = 'Dota 2',
            defaults = {
                "sheetid": '1vF3d0ZHPfHUaW8sdl56gkdm4H8la7QS80DCVLz3kC14',
                "worksheetid": 190455318,
                "cells": {
                            "1": {
                                "Declined": "B2",
                                "Attending": "A2",
                                "Tentative": "None"
                            },
                            "2": {
                                "Carry": "A7",
                                "Midlane": "A7",
                                "Offlane": "A7",
                                "Soft Support": "A7",
                                "Hard Support": "A7"
                            },
                            "cell_date": "d1",
                            "cell_desc": "d2",
                            "cell_link": "none",
                            "cell_title": "e1"
                        },
                "lnkd_opt_presets": [1, 3],
                "thumb_url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/570/0bbb630d63262dd66d2fdd0f7d37e8661a410075.jpg",
                "emoji": "<:dota2:1393621659075874856>"
            },
        )
        
        template, _ = await sync_to_async(Templates.objects.update_or_create)(
            gid = baastCnf,
            name = 'Tournament',
            defaults = {
                "sheetid": '1vF3d0ZHPfHUaW8sdl56gkdm4H8la7QS80DCVLz3kC14',
                "worksheetid": 1865496485,
                "cells": {
                            "1": {
                                "Declined": "B2",
                                "Attending": "A2",
                                "Tentative": "None"
                            },
                            "cell_date": "d1",
                            "cell_desc": "d2",
                            "cell_link": "none",
                            "cell_title": "e1"
                        },
                "lnkd_opt_presets": [1],
                "thumb_url": "None",
                "emoji": "🏆"
            },
        )
        
        template, _ = await sync_to_async(Templates.objects.update_or_create)(
            gid = baastCnf,
            name = 'Star Citizen',
            defaults = {
                "sheetid": '1vF3d0ZHPfHUaW8sdl56gkdm4H8la7QS80DCVLz3kC14',
                "worksheetid": 206301442,
                "cells": {
                            "1": {
                                "Declined": "B2",
                                "Attending": "A2",
                                "Tentative": "None"
                            },
                            "cell_date": "none",
                            "cell_desc": "none",
                            "cell_link": "none",
                            "cell_title": "d1"
                        },
                "lnkd_opt_presets": [1],
                "thumb_url": "https://yt3.ggpht.com/ytc/AKedOLTniIZwSZulOVuM_i1bLD4YLi7NtK4UhBc4xULAKw=s900-c-k-c0x00ffffff-no-rj",
                "emoji": "<:sc:1393621787920699442>"
            },
        )

    async def setup_options(self):
        baastCnf = await sync_to_async(Config.objects.get)(guild=MAIN_GUILD_ID)
        
        preset, _ = await sync_to_async(Option_Presets.objects.update_or_create)(
            gid = baastCnf,
            name = 'Default',
            defaults = {
                "options": [{"label": "Attending", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Declined", "colour":"red", "istentative": False, "send_notifcations": False, "is_attending": False},
                            {"label": "Tentative", "colour":"blurple", "istentative": True, "send_notifcations": True, "is_attending": False}],
                "len": 3,
                "use_capacity": True,
                "split_capacity": False,
            }
        )
        
        preset, _ = await sync_to_async(Option_Presets.objects.update_or_create)(
            gid = baastCnf,
            name = 'Dota 2',
            defaults = {
                "options": [{"label": "Carry", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Midlane", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Offlane", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Soft Support", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Hard Support", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True}],
                "len": 5,
                "use_capacity": True,
                "split_capacity": True,
            }
        )
        
        preset, _ = await sync_to_async(Option_Presets.objects.update_or_create)(
            gid = baastCnf,
            name = 'Squad',
            defaults = {
                "options": [{"label": "Squad Lead", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Medic", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "Rifleman", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "MG", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "LAT", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
                            {"label": "HAT", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True}],
                "len": 6,
                "use_capacity": True,
                "split_capacity": True,
            }
        )
        
        # preset, _ = await sync_to_async(Option_Presets.objects.update_or_create)(
        #     gid = baastCnf,
        #     name = 'Default',
        #     defaults = {
        #         "options": [{"label": "Attending", "colour":"green", "istentative": False, "send_notifcations": True, "is_attending": True},
        #                     {"label": "Declined", "colour":"red", "istentative": False, "send_notifcations": True, "is_attending": True},
        #                     {"label": "Tentative", "colour":"blurple", "istentative": False, "send_notifcations": True, "is_attending": True}],
        #         "len": 3,
        #         "use_capacity": True,
        #         "split_capacity": False,
        #     }
        # )

