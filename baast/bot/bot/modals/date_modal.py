import arrow

import lightbulb
from hikari import MessageFlag, ResponseType

from bot.bot.utils.exceptions import DatetimeError
from bot.bot.utils.util import validate_datetime

class DateModal(lightbulb.components.Modal):
    value: arrow.Arrow = None
    allow_none: bool = False
    require_time: bool = True
    
    
    def __init__(self, date: arrow.Arrow = None, allow_none: bool = False, require_time: bool = True) -> None:
        self.value = date
        self.allow_none = allow_none
        self.require_time = require_time
        
        self.text = self.add_short_text_input("Date", value=date.format("DD/MM/YYYY h:mm A ZZZ") if date else "None", required=True,
                                              placeholder=f'Day/Month/Year {"HH:MM TZ" if self.require_time else ""} -  20/04/2223 '
                                              f'{"8:00 PM UTC" if self.require_time else ""}  '
                                              f'-  20/04/2223 {"20:00 UTC" if self.require_time else ""} {"- None" if self.allow_none else ""}')

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v: str = ctx.value_for(self.text)
        
        if v.lower() == "none":
            if self.allow_none:
                self.value = None
                return
            else:
                await ctx.respond(content="### Error\nStart time can\'t be 'None'! Try Again...", flags=MessageFlag.EPHEMERAL)
                raise ValueError("None")
        else:
            valid, arDateTime = validate_datetime(v.upper(), require_time=self.require_time)
            
            
            if valid == DatetimeError.NotValid:
                await ctx.respond(content=f"### Error\nInvalid datetime format.\n```Day/Month/Year {"Hour:Minute TZ" if self.require_time else ""}```"
                                    f"\n**Examples:**\n```DD/MM/YYYY {"8:00 PM UTC" if self.require_time else ""}\nDD/MM/YYYY {"16:00 CT" if self.require_time else ""}``` {"or ```None```" if self.allow_none else ""}", flags=MessageFlag.EPHEMERAL)
            elif valid == DatetimeError.PreNow:
                await ctx.respond(content="### Error\nStart time can\'t be in the past! Try Again...", flags=MessageFlag.EPHEMERAL)
            else:
                self.value = arDateTime
            
                await ctx._create_initial_response(
                        ResponseType.DEFERRED_MESSAGE_UPDATE,
                        flags=MessageFlag.EPHEMERAL,
                    )
        