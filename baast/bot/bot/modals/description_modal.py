import lightbulb

from hikari import MessageFlag, ResponseType

class DescriptionModal(lightbulb.components.Modal):
    value = None
    
    def __init__(self, description: str = None) -> None:
        self.value = description
        
        self.text = self.add_paragraph_text_input("Enter the Event Description or 'None'", value=description, max_length=1000, required=False)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self.text)
        if v == "None":
            v = None
        
        self.value = v
        await ctx._create_initial_response(
                ResponseType.DEFERRED_MESSAGE_UPDATE,
                flags=MessageFlag.EPHEMERAL,
            )
        