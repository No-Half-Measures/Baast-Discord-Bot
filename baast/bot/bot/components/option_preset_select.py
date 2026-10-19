from asgiref.sync import sync_to_async

from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import ComponentInteraction, Snowflakeish, Embed, ButtonStyle, Emoji, Color, undefined

from app.models import Config, Templates, Option_Presets
from bot.bot.utils.exceptions import SetupCancel

class OptionPresetSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected: int
    
    cancel_setup: bool = False
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.mainContext = None
        self.snowflake = -1
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected = None
        
        self.embed = None
        
        super().__init__()
    
    async def create(self, ctx: Context, template: Templates, snowflake: Snowflakeish = None) -> None:
        
        self.max = 1
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = 'Select a Option Preset.',
            description = None,
            color = Color(0xf3df73)
        )
        
        options_list: list[Option_Presets] = await sync_to_async(template.get_options)() # NEED a guild filter so people don't get other peopls options

        split_options = [
            options_list[i:i + 20] for i in range(0, len(options_list), 20)
        ]  # Split the list into chunks of size 20
        

        for i, s in enumerate(split_options, 0):
            selectList = []
            
            for op in s:
                selectList.append(TextSelectOption(label=op.name, value=str(op.id), description=op.to_string[0:100]))
            
            self.selction_stages.append(selectList)
        
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select, max_values=self.max)
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel"
        )
        
        self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
        
        return self
    
    async def on_select(self, ctx: components.MenuContext) -> None:
        if ctx.selected_values_for(self.select)[0] != "-1":
            self.selected = ctx.selected_values_for(self.select)[0]
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        if self.currentStage == self.selction_stages.__len__() - 1:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        else:
            self.currentStage += 1
            
            try:
                self.select.options = self.selction_stages[self.currentStage]
            except IndexError:
                print(f"No more pages {self.selction_stages.__len__()}")
                await ctx.defer(edit=True)
                ctx.stop_interacting()
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            
            if isinstance(self.mainContext, ComponentInteraction):
                await self.mainContext.edit_initial_response(self.embed, components=self)
            else:
                await self.mainContext.edit_response(self.snowflake, self.embed, components=self)
                
            await ctx.defer(edit=True)
    
    async def on_cancel(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        self.cancel_setup = True
        ctx.stop_interacting()
