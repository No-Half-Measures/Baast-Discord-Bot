import loguru

logger = loguru.logger

class BaseDjangoDiscordException(Exception):
    """
    Base exception for all intentional errors from this library
    """
    
    def __init__(self, msg):
        self.msg = msg
        logger.exception(msg)  # use your logging things here

    def __str__(self):
        return self.msg


class BotNotReadyYet(BaseDjangoDiscordException):
    """
    The bot isn't ready yet, someone used the library incorrectly?
    """
    
class BotNotRunning(BaseDjangoDiscordException):
    """
    The bot isn't running
    """


class MissingConfiguration(BaseDjangoDiscordException):
    """
    Something about the configuration is wrong, see the message for more details
    """