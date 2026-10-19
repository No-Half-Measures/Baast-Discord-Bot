from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import Snowflakeish, Embed, ButtonStyle, Color

from app.models import Events, Config

from bot.bot.utils.exceptions import NoValues, SetupCancel

from loguru import logger

class EventSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 1
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected_events: list[str] = []
    
    cancel_setup: bool = False
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.mainContext = None
        self.snowflake = -1
        self.max = 1
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_events = []
        
        self.embed = None
    
    async def create(self, ctx: Context, events: list[Events], snowflake: Snowflakeish = None, max: int = 1, title: str = "Select an Event") -> None:
        
        self.max = max
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = title,
            color = Color(0xf3df73)
        )
        
        guild = await ctx.client.rest.fetch_guild(ctx.guild_id)
        
        
        try:
            # Split roles into 20s for pagination
            splitRoles: list[list[Events]] = [events[i:i + 20] for i in range(0, len(events), 20)]
        except Exception as e:
            logger.error(f'Error splitting roles: {str(e)}')
        
        for i, s in enumerate(splitRoles, 1):
            selectMenus = []

            if (splitRoles.__len__() > 1) and i != splitRoles.__len__() - 1:
                selectMenus.append(TextSelectOption(label="None", value="0"))
            
            for r in s:
                selectMenus.append(TextSelectOption(label=r.title, value=str(r.id)))
                
            self.selction_stages.append(selectMenus)
            
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select, 
                                           max_values=self.max if self.selction_stages[self.currentStage].__len__() > self.max else self.selction_stages[self.currentStage].__len__())
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel"
        )
        
        self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
        
        return self
    
    async def on_select(self, ctx: components.MenuContext) -> None:
        if ctx.selected_values_for(self.select)[0] != "0":
            self.selected_events.extend(ctx.selected_values_for(self.select))
        
        if self.selected_events.__len__() == self.max:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        else:
            self.currentStage += 1
            
            self.previous_row()
            self.clear_current_row()
            
            try:
                self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select, 
                                                   max_values=self.max - self.selected_events.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__())
            except IndexError:
                print(f"No more pages {self.selction_stages.__len__()}")
                await ctx.defer(edit=True)
                ctx.stop_interacting()
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            await self.mainContext.edit_response(self.snowflake, self.embed, components=self)
    
    async def on_cancel(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        self.cancel_setup = True
        ctx.stop_interacting()
