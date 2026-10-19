from asgiref.sync import sync_to_async

from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import Snowflakeish, Embed, User, ButtonStyle, Role, Color, LazyIterator, OwnGuild

from bot.bot.utils.exceptions import NoValues, SetupCancel

from loguru import logger

##
# This gets the guilds the bot is in and if the user arg is not none filters guilds only the user is in
##
class GuildSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 20
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected_guilds: list[str] = []
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.mainContext = None
        self.snowflake = -1
        self.max = 1
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_guilds = []
        
        self.embed = None
    
    async def create(self, ctx: Context, snowflake: Snowflakeish = None, max: int = 1, user: User = None, myGuilds: list[OwnGuild] = None, title: str = "Select Guild(s)") -> None:
        self.max = max
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = title,
            color = Color(0xf3df73)
        )
        
        guild = await ctx.client.rest.fetch_guild(ctx.guild_id)
        
        try:
            if myGuilds == None:
                myGuilds = []
                guilds: LazyIterator[OwnGuild] = ctx.client.rest.fetch_my_guilds()
                async for g in guilds:
                    myGuilds.append(g)
        except Exception as e:
            logger.error(f'Error fetching guilds: {str(e)}')
            
        cachedGuilds: list[OwnGuild] = []
        
        try:
            if user is not None:
                for g in myGuilds:
                    if g.id != guild.id:
                        if await g.app.rest.fetch_member(g, user):
                            cachedGuilds.append(g)
            else:
                cachedGuilds = list(myGuilds)
        except Exception as e:
            logger.error(f'Error processing guilds: {str(e)}')
        
        if len(cachedGuilds) < 1:
            raise NoValues
        
        try:
            # Split roles into 20s for pagination
            splitGuilds: list[list[Role]] = [cachedGuilds[i:i + 20] for i in range(0, len(cachedGuilds), 20)]
        except Exception as e:
            logger.error(f'Error splitting roles: {str(e)}')
        
        try:
            for i, s in enumerate(splitGuilds, 1):
                selectMenus = []

                if splitGuilds.__len__() > 1 and i != splitGuilds.__len__() - 1:
                    selectMenus.append(TextSelectOption(label="None", value="0"))
                
                for g in s:
                    selectMenus.append(TextSelectOption(label=g.name, 
                                                        value=str(g.id)))
                    
                self.selction_stages.append(selectMenus)
        except Exception as e:
            logger.error(f'Error adding guilds to select menus: {str(e)}')
        
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select, 
                                           max_values=self.max if self.selction_stages[self.currentStage].__len__() > self.max else self.selction_stages[self.currentStage].__len__())
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel"
        )
        
        # self.btn2 = self.add_interactive_button(
        #     ButtonStyle.PRIMARY,
        #     self.on_refresh,
        #     label="Refresh"
        # )
        
        self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
        
        return self
    
    async def on_select(self, ctx: components.MenuContext) -> None:
        if ctx.selected_values_for(self.select)[0] != "0":
            self.selected_guilds.extend(ctx.selected_values_for(self.select))
        
        if self.selected_guilds.__len__() == self.max or self.currentStage == self.selction_stages.__len__() - 1:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        else:
            self.currentStage += 1
            
            try:
                self.select.max_values = self.max - self.selected_guilds.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_guilds.__len__() else self.selction_stages[self.currentStage].__len__()
                self.select.options = self.selction_stages[self.currentStage]
            except IndexError:
                print(f"No more pages {self.selction_stages.__len__()}")
                await ctx.defer(edit=True)
                ctx.stop_interacting()
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            await self.mainContext.edit_response(self.snowflake, self.embed, components=self)
            await ctx.defer(edit=True)
    
    async def on_cancel(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        ctx.stop_interacting()
        raise SetupCancel
        
    async def on_refresh(self, ctx: components.MenuContext) -> None:
        self.previous_row()
        self.clear_current_row()
        
        try:
            self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select,
                                                max_values=self.max - self.selected_guilds.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__())
        except IndexError:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        
        await self.mainContext.edit_response(self.snowflake, self.embed, components=self)
