import lightbulb
from hikari import MessageFlag, ResponseType, Color


def isNumber(value: str) -> bool:
    try:
        val = int(value)
    except ValueError:
        return False
    return True

class CapacityModal(lightbulb.components.Modal):
    value = 100
    
    def __init__(self, capacity: int = 100) -> None:
        self.value = capacity
        
        self.text = self.add_short_text_input("Capacity", placeholder="Type `None` for no limit.\nUp to 100 attendees are allowed.", 
                                              value=self.value, required=True, max_length=3)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self.text)
        if v == "None":
            v = None
            
            self.value = v    
            await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
            return
            
            
        if isNumber(v) == False:
            await ctx.respond(content="### Error\nYou did not enter a number.\nPlease enter a number between 1-100 or `None` for no limit!", flags=MessageFlag.EPHEMERAL)
        else:
            self.value = int(v)    
            await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
        