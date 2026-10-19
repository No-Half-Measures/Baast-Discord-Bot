import lightbulb

from hikari import MessageFlag, ResponseType

class ImageModal(lightbulb.components.Modal):
    value = None
    
    def __init__(self, img_url: str = None) -> None:
        self.value = img_url
        
        self.text = self.add_short_text_input("Enter the Event Description or 'None'", value=img_url, required=False,
                                                  placeholder="URL or 'None' for no image.")

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self.text)
        if v == "None":
            v = None
        
        self.value = v
        await ctx._create_initial_response(
                ResponseType.DEFERRED_MESSAGE_UPDATE,
                flags=MessageFlag.EPHEMERAL,
            )
        