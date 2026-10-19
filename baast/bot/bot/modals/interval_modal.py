import sys

import lightbulb
from hikari import MessageFlag, ResponseType

from bot.bot.utils.util import validate_interval

from loguru import logger

class IntervalModal(lightbulb.components.Modal):
    value: tuple[int,int,int] = None
    
    def __init__(self, interval: int = 0) -> None:
        self.value = interval
        
        self.text = self.add_short_text_input("Date", value=f"{self.value}D", 
                                                required=False, placeholder='7D')

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v: str = ctx.value_for(self.text)
        
        try:
            interval = validate_interval(v)
        except ValueError as e:
            await ctx.respond(content=e, flags=MessageFlag.EPHEMERAL)
            return None
        except:
            logger.error(sys.exc_info())
            return None
        else:
            self.value = interval
        
            await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
        