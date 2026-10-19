import lightbulb
from hikari import MessageFlag, ResponseType

class TitleDescriptionModal(lightbulb.components.Modal):
    title: str = "New Event"
    description: str | None = "None"
    
    def __init__(self, title: str = "New Event", description: str | None = "None") -> None:
        self.title = title
        self.description = description if description else "None"
        
        self._title = self.add_short_text_input("Enter the Event Title", value=self.title, required=True)
        self._description = self.add_paragraph_text_input("Enter the Event Description", value=self.description, required=False)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self._title)
        
        b = ctx.value_for(self._description)
        if b == "None" or b == "" or b == None:
            b = None
            
        self.title = v
        self.description = b
        await ctx._create_initial_response(
                ResponseType.DEFERRED_MESSAGE_UPDATE,
                flags=MessageFlag.EPHEMERAL,
            )
        