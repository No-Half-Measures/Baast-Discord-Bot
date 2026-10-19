import arrow, sys

import lightbulb
from hikari import Embed, MessageFlag, ResponseType

from bot.bot.utils.exceptions import DatetimeError
from bot.bot.utils.util import validate_datetime, validate_interval

from loguru import logger


class RecurringModal(lightbulb.components.Modal):
    until: arrow.Arrow = None
    allow_none: bool = False
    require_time: bool = True
    
    interval: tuple[int,int,int] = None
    
    
    def __init__(self, date: arrow.Arrow = None, interval: tuple[int,int,int] = None, allow_none: bool = False, require_time: bool = True) -> None:
        self.recurring_until = date
        self.interval = interval
        self.allow_none = allow_none
        self.require_time = require_time
        
        self._reccur_interval = self.add_short_text_input("Repeat Interval", value=f"{self.interval}D", required=True, placeholder='7D')
        
        self._reccur_until = self.add_short_text_input("Repeat Until", value=date.format("DD/MM/YYYY h:mm A ZZZ") if date else "None", required=True,
                                              placeholder=f'Day/Month/Year {"HH:MM TZ" if self.require_time else ""} -  20/04/2223 '
                                              f'{"8:00 PM UTC" if self.require_time else ""}  '
                                              f'-  20/04/2223 {"20:00 UTC" if self.require_time else ""} {"- None" if self.allow_none else ""}')
    

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        # Recurring Until
        v: str = ctx.value_for(self._reccur_until)
        
        if v.lower() == "none" and self.allow_none:
            self.recurring_until = None
            
            response = await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
        else:
            valid, arDateTime = validate_datetime(v.upper(), require_time=self.require_time)
            
            if valid == DatetimeError.NotValid:
                await ctx.respond(content=f"### Error\nInvalid datetime format.\n```Day/Month/Year {"Hour:Minute TZ" if self.require_time else ""}```"
                                  f"\n**Examples:**\n```DD/MM/YYYY {"8:00 PM UTC" if self.require_time else ""}\nDD/MM/YYYY {"16:00 CT" if self.require_time else ""}``` {"or ```None```" if self.allow_none else ""}", flags=MessageFlag.EPHEMERAL)
                return None
            elif valid == DatetimeError.PreNow:
                await ctx.respond(content="### Error\nStart time can\'t be in the past! Try Again...", flags=MessageFlag.EPHEMERAL)
                return None
            else:
                self.recurring_until = arDateTime
                
        #
        # Interval
        
        v: str = ctx.value_for(self._reccur_interval)
        
        try:
            interval = validate_interval(v)
        except ValueError:
            await ctx.respond(content=Embed(description="Invalid unit. Use D (days), W (weeks), or M (months). **Example:**`7D` or `6M"), flags=MessageFlag.EPHEMERAL)
            return None
        except Exception as e:
            logger.error(f'Error validating interval: {e}')
            return None
        else:
            self.interval = interval
        
        
        await ctx.edit_response( response, 
                ResponseType.DEFERRED_MESSAGE_UPDATE,
            )
        