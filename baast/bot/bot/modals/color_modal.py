import lightbulb
from hikari import MessageFlag, ResponseType, Color

class ColorModal(lightbulb.components.Modal):
    value = '#f3df73'
    
    def __init__(self, color: str = '#f3df73') -> None:
        self.value = color
        
        self.text = self.add_short_text_input("Color", placeholder="Enter Color or 'None' for default color.", value=color, required=True, max_length=7)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self.text)
        if v == "None":
            v = '#f3df73'
            
        try:
            Color.of(v)
        except ValueError:
            await ctx.respond(content="### Error\nInvalid color. Please enter a valid hex color code.\n**Example:** `#f3df73`", flags=MessageFlag.EPHEMERAL)
        else:
            self.value = v    
            await ctx._create_initial_response(
                    ResponseType.DEFERRED_MESSAGE_UPDATE,
                    flags=MessageFlag.EPHEMERAL,
                )
        