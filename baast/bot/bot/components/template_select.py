from asgiref.sync import sync_to_async

from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import ComponentInteraction, Snowflakeish, Embed, ButtonStyle, Emoji, Color, UNDEFINED, UnicodeEmoji

from app.models import Config, Templates
from bot.bot.utils.exceptions import SetupCancel

from loguru import logger

class TemplateSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected: int
    
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
        
        self.cancel_setup = False
        
        super().__init__()
    
    async def create(self, ctx: Context, snowflake: Snowflakeish = None) -> None:
        
        self.max = 1
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = 'Select a Template.',
            description = None,
            color = Color(0xf3df73)
        )
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=ctx.guild_id)
        except Exception as e:
            logger.error(f"TemplateSelect: {ctx.guild_id} - {e}")
            return

        try:
            defaults = await sync_to_async(Templates.objects.filter)(gid = 1)
        except Exception as e:
            logger.error(f"TemplateSelect: {ctx.guild_id} - {e}")
            return
        
        guildsTmpts = None
        if config.is_premium:
            try:
                guildsTmpts = await sync_to_async(Templates.objects.filter)(gid=config.id)
            except Exception as e:
                logger.error(f"TemplateSelect: {ctx.guild_id} - {e}")
                return
        
        # Combine templates: guild templates + defaults
        if guildsTmpts is not None:
            # If guild has templates, combine them with defaults
            combined_queryset = guildsTmpts | defaults
            templates_list = await sync_to_async(list)(combined_queryset)
        else:
            # If no guild templates, just use defaults
            templates_list = await sync_to_async(list)(defaults)

        split_templates = [
            templates_list[i:i + 20] for i in range(0, len(templates_list), 20)
        ]  # Split the list into chunks of size 20
        

        for i, s in enumerate(split_templates, 1):
            selectList = []
            
            if split_templates.__len__() > 1 and i != split_templates.__len__() - 1:
                selectList.append(TextSelectOption(label="None", value="-1"))
            
            for t in s:
                emoji = None
                if t.emoji:  # Check if emoji is not None or empty
                    try:
                        emoji = Emoji.parse(t.emoji)
                    except Exception as e:
                        logger.warning(f"Failed to parse emoji '{t.emoji}' for template {t.name}: {e}")
                        emoji = None
                
                try:
                    selectList.append(TextSelectOption(
                        label=t.name, 
                        value=str(t.id), 
                        emoji=emoji if emoji and not isinstance(emoji, UnicodeEmoji) else UNDEFINED
                    ))
                except Exception as e:
                    logger.error(f"Failed to create TextSelectOption for template {t.name}: {e}")
            
            self.selction_stages.append(selectList)
        
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select, max_values=self.max)
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel",
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
            
            self.previous_row()
            self.clear_current_row()
            
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
