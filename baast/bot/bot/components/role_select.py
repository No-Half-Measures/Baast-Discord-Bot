from hikari.interactions import ComponentInteraction
from lightbulb import components, Context, Client
from lightbulb.components import TextSelectOption
from hikari import Snowflakeish, Embed, Guild, ButtonStyle, Role, Message, Color

from bot.bot.utils.exceptions import NoValues, SetupCancel

from loguru import logger
from cache.helpers import _safe_get_cache_view

class RoleSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 20
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected_roles: list[str] = []
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.mainContext = None
        self.snowflake = -1
        self.max = 20
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_roles = []
        
        self.embed = None
    
    async def create(self, ctx: Context, snowflake: Snowflakeish = None, max: int = 20, reqNone: bool = True) -> None:
        
        self.max = max
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = 'Select Role(s)',
            color = Color(0xf3df73)
        )
        
        
        guild = await ctx.client.rest.fetch_guild(ctx.guild_id)
        roles = _safe_get_cache_view(guild.get_roles, f"guild {ctx.guild_id} roles")

        if len(roles) < 1:
            raise NoValues
        
        try:
            # Split roles into 20s for pagination
            splitRoles: list[list[Role]] = [roles[i:i + 20] for i in range(0, len(roles), 20)]
        except Exception as e:
            logger.error(f'Error splitting roles: {str(e)}')
        
        for i, s in enumerate(splitRoles, 1):
            selectMenus = []

            if (reqNone or splitRoles.__len__() > 1) and i != splitRoles.__len__() - 1:
                selectMenus.append(TextSelectOption(label="None", value="0"))
            
            for r in s:
                selectMenus.append(TextSelectOption(label="Everyone" if r.id == guild.id else r.name, 
                                                    value=str(r.id)))
                
            self.selction_stages.append(selectMenus)
            
        
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
            self.selected_roles.extend(ctx.selected_values_for(self.select))
        
        if self.selected_roles.__len__() == self.max or self.currentStage == self.selction_stages.__len__() - 1:
            ctx.stop_interacting()
            await ctx.defer(edit=True)
        else:
            self.currentStage += 1
            
            try:
                self.select.max_values = self.max - self.selected_roles.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__()
                self.select.options = self.selction_stages[self.currentStage]
                
                #self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select,
                #                                   max_values=self.max - self.selected_roles.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__())
            except IndexError:
                ctx.stop_interacting()
                return
            except Exception as e:
                logger.error(f"[ROLE SELECT] Error while selecting: {e}")
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            
            if isinstance(self.mainContext, ComponentInteraction):
                await self.mainContext.edit_initial_response(self.embed, components=self)
            else:
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
                                                max_values=self.max - self.selected_roles.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__())
        except IndexError:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        
        await self.mainContext.edit_response(self.snowflake, self.embed, components=self)
        
        
        
class RoleSelect_M(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 20
    
    # Data
    currentStage: int = 0
    selected_roles: list[str] = []
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.max = 20
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_roles = []
        
        self.embed = None
    
    async def create(self, message: Message, guild: Guild, client: Client, max: int = 20, reqNone: bool = True) -> None:
        self.message = message
        self.max = max
        
        self.embed = Embed(
            title = 'Select Role(s)',
            color = Color(0xf3df73)
        )
        
        roles = _safe_get_cache_view(guild.get_roles, f"guild {guild.id} roles")

        if len(roles) < 1:
            raise NoValues
        
        try:
            # Split roles into 20s for pagination
            splitRoles: list[list[Role]] = [roles[i:i + 20] for i in range(0, len(roles), 20)]
        except Exception as e:
            logger.error(f'Error splitting roles: {str(e)}')
        
        for i, s in enumerate(splitRoles, 1):
            selectMenus = []

            if (reqNone or splitRoles.__len__() > 1) and i != splitRoles.__len__() - 1:
                selectMenus.append(TextSelectOption(label="None", value="0"))
            
            for r in s:
                selectMenus.append(TextSelectOption(label="Everyone" if r.id == guild.id else r.name, 
                                                    value=str(r.id)))
                
            self.selction_stages.append(selectMenus)
            
        
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
            self.selected_roles.extend(ctx.selected_values_for(self.select))
        
        if self.selected_roles.__len__() == self.max or self.currentStage == self.selction_stages.__len__() - 1:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        else:
            self.currentStage += 1
            
            try:
                self.select.max_values = self.max - self.selected_roles.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__()
                self.select.options = self.selction_stages[self.currentStage]
            except IndexError:
                await ctx.defer(edit=True)
                ctx.stop_interacting()
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            await self.message.edit(self.embed, components=self)
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
                                                max_values=self.max - self.selected_roles.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_roles.__len__() else self.selction_stages[self.currentStage].__len__())
        except IndexError:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        
        await self.message.edit(self.embed, components=self)
