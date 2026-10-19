import sys

import lightbulb
from hikari import MessageFlag, ResponseType

from bot.bot.utils.util import HumanizeReminderShort, validate_time

from loguru import logger

class TimeModal(lightbulb.components.Modal):
    value: tuple[int,int,int] = None
    
    def __init__(self, time: tuple[int,int,int] = [0,0,0]) -> None:
        self.value = time
        
        self.text = self.add_short_text_input("Date", value=HumanizeReminderShort(time), 
                                                required=False, placeholder='3D 00:00')

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v: str = ctx.value_for(self.text)
        
        try:
            h,m,s = validate_time(v)
        except ValueError:
            await ctx.respond(content="### Error\nInvalid Time format.\n`ddD MM:SS` or `HH:MM:SS`\n**Example:**\n`3D 12:00` or `72:12:00`", flags=MessageFlag.EPHEMERAL)
            return None
        except:
            logger.error(sys.exc_info())
            return None
        else:
            self.value = h,m,s
        
            await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
        