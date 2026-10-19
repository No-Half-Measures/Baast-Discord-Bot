from typing import ClassVar

from bot.exceptions import BotNotReadyYet
from bot.signals import bot_error, bot_ready, command_error

from bot.bot.app import Baast

class DjangoDiscordPlugin():
    command_definitions = []

    bot_proxy: ClassVar = None

    @property
    def bot(self) -> Baast:
        the_bot = type(self).bot_proxy
        if not the_bot:
            raise BotNotReadyYet("The bot isn't ready yet! Have you started the bot?")
        return the_bot
