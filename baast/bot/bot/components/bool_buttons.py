from lightbulb import components
from hikari import ButtonStyle

class BooleanButton(components.Menu):
    value = False
    
    def __init__(self, true_lable: str = "Yes", false_label: str = "No"):
        self.value = False
        
        self.true = self.add_interactive_button(
            ButtonStyle.SUCCESS,
            self.on_true,
            label=true_lable,
        )
        
        self.false = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_false,
            label=false_label,
        )

    async def on_true(self, ctx: components.MenuContext) -> None:
        self.value = True
        await ctx.defer(edit=True)
        ctx.stop_interacting()
            
    async def on_false(self, ctx: components.MenuContext) -> None:
        self.value = False
        await ctx.defer(edit=True)
        ctx.stop_interacting()
    