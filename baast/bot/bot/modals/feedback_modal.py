import lightbulb
from hikari import MessageFlag, ResponseType

class FeedbackModal(lightbulb.components.Modal):
    feedback: str | None = "None"
    
    def __init__(self, feedback: str = "None") -> None:
        self.feedback = feedback if feedback else "None"
        
        self._feedback = self.add_paragraph_text_input("Enter your feedback", value=self.feedback, required=True)

    async def on_submit(self, ctx: lightbulb.components.ModalContext) -> None:
        v = ctx.value_for(self._feedback)
        if v == "None" or v == "" or v == None:
            v = None
            
        self.feedback = v
        await ctx._create_initial_response(
                ResponseType.DEFERRED_MESSAGE_UPDATE,
                content=f"Thank you for your feedback! We'll use it to improve Baast for you and other users."
            )