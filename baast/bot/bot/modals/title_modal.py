import lightbulb
from hikari import MessageFlag, ResponseType

class TitleModal(lightbulb.components.Modal):
    value = "New Event"
    
    def __init__(self, title: str = "New Event") -> None:
        self.value = title
        
        self.text = self.add_short_text_input("Enter the Event Title", value=title, required=True)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self.text)
        if v == "None":
            v = None
            
        self.value = v    
        await ctx._create_initial_response(
                ResponseType.DEFERRED_MESSAGE_UPDATE,
                flags=MessageFlag.EPHEMERAL,
            )
        