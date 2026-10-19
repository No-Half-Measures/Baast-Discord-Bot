import sys

from lightbulb import components, Context, Client
from lightbulb.components import TextSelectOption
from hikari import ComponentInteraction, Snowflakeish, Embed, Permissions, ButtonStyle, GuildChannel, Emoji, Color, Message, Guild

from bot.bot.utils.util import HasChannelPermission
from bot.bot.utils.exceptions import NoValues, SetupCancel

from loguru import logger

class ChannelSelect(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 20
    snowflake: Snowflakeish = -1
    mainContext: Context = None
    
    # Data
    currentStage: int = 0
    selected_channels: list[str] = []
    
    cancel_setup: bool = False
    
    def __init__(self):
        ###
        # This is to reset values as it seems lightbulb reuses objects.....
        ###
        self.mainContext = None
        self.snowflake = -1
        self.max = 20
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_channels = []
        
        self.embed = None
        
        self.cancel_setup = False
        
        super().__init__()
    
    async def create(self, ctx: Context, client: Client, snowflake: Snowflakeish = None, max: int = 20, reqNone: bool = True,
                     title: str = "Select Channel(s)", description: str = None, fav_channels: list[int] = None,
                            reqPerms: Permissions = (Permissions.SEND_MESSAGES | Permissions.SEND_MESSAGES_IN_THREADS |
                                Permissions.VIEW_CHANNEL | Permissions.CREATE_PUBLIC_THREADS | Permissions.CREATE_PRIVATE_THREADS | 
                                Permissions.MANAGE_THREADS)) -> None:
        
        self.max = max
        self.snowflake = snowflake
        self.mainContext = ctx
        
        self.embed = Embed(
            title = title,
            description = F"""{description}\n
            {(await client.rest.fetch_my_user()).mention} requires the following permissions: ```{reqPerms.__str__().replace("|", ", ")}```""",
            color = Color(0xf3df73)
        )
        
        
        guild = await client.rest.fetch_guild(ctx.guild_id)
    
        cachedChannels = await client.rest.fetch_guild_channels(guild)

        textChnls = []
        for val in cachedChannels:
            val: GuildChannel = val
            if val.type.value == 0:
                if HasChannelPermission(val, guild, guild.get_my_member(), reqPerms):
                    textChnls.append({"valid":True, "channel":val})
                elif HasChannelPermission(val, guild, guild.get_my_member(), Permissions.SEND_MESSAGES | Permissions.VIEW_CHANNEL):#MANAGE_THREADS
                    for perm in reqPerms:
                        if not HasChannelPermission(val, guild, guild.get_my_member(), perm):
                            textChnls.append({"valid":False, "channel":val, "perm":perm})
                            break

        if len(textChnls) < 1:
            raise NoValues
        
        # Sort channels so favorites appear first
        if fav_channels:
            textChnls.sort(key=lambda x: x["channel"].id not in fav_channels)

        split_templates = [
            textChnls[i:i + 20] for i in range(0, len(textChnls), 20)
        ]  # Split the list into chunks of size 20
        
        for i, s in enumerate(split_templates, 0):
            selectMenus = []
            
            if (reqNone or split_templates.__len__() > 1) and i != split_templates.__len__() - 1:
                selectMenus.append(TextSelectOption(label="None" if reqNone else "Next Page ➡️", value="0", emoji=Emoji.parse('<:validchannel:1120728238667346051>')))
            
            for t in s:
                selectMenus.append(TextSelectOption(label=t["channel"].name, 
                                                    value=str(t["channel"].id), 
                                                    description=None if t["valid"] else f'Missing Permission:\n {str(t["perm"].name)}',
                                                    emoji=Emoji.parse('<:validchannel:1120728238667346051>' if t["valid"] else '<:invalidchannel:1120728255633301526>')))
                
            self.selction_stages.append(selectMenus)
        
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select,
                                           max_values=self.max if self.selction_stages[self.currentStage].__len__() > self.max else self.selction_stages[self.currentStage].__len__())
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel",
            #custom_id="cancel_button",
        )
        
        self.btn2 = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.on_refresh,
            label="Refresh",
            #custom_id="refresh_button",
        )
        
        self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
        
        return self
    
    async def on_select(self, ctx: components.MenuContext) -> None:
        if ctx.selected_values_for(self.select)[0] != "0":
            self.selected_channels.extend(ctx.selected_values_for(self.select))
        
        if self.selected_channels.__len__() == self.max or self.currentStage == self.selction_stages.__len__() - 1:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        else:
            self.currentStage += 1
            
            try:
                self.select.max_values = self.max - self.selected_channels.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__()
                self.select.options = self.selction_stages[self.currentStage]
                # self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select,
                #                                    max_values=self.max - self.selected_channels.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__())
            except IndexError:
                print(f"No more pages {self.selction_stages.__len__()}")
                await ctx.defer(edit=True)
                ctx.stop_interacting()
                return
            except Exception as e:
                logger.error(f"Error while selecting: {e}")
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
            
    async def on_refresh(self, ctx: components.MenuContext) -> None:
        self.previous_row()
        self.clear_current_row()
        
        try:
            self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_refresh,
                                                max_values=self.max - self.selected_channels.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__())
        except IndexError:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
            raise IndexError
        
        if isinstance(self.mainContext, ComponentInteraction):
            await self.mainContext.edit_initial_response(self.embed, components=self)
        else:
            await self.mainContext.edit_response(self.snowflake, self.embed, components=self)

##
# The Message.Edit Version
##
class ChannelSelect_M(components.Menu):
    # Defaults
    selction_stages: list[list[TextSelectOption]] = []
    max = 20
    
    # Data
    currentStage: int = 0
    selected_channels: list[str] = []
    
    def __init__(self):
        self.max = 20
        self.selction_stages = []
        
        self.currentStage = 0
        self.selected_channels = []
        
        self.embed = None
        
        super().__init__()
    
    async def create(self, message: Message, guild:Guild, client: Client, max: int = 20, reqNone: bool = True, fav_channels: list[int] = None,
                            reqPerms: Permissions = (Permissions.SEND_MESSAGES | Permissions.SEND_MESSAGES_IN_THREADS |
                                Permissions.VIEW_CHANNEL | Permissions.CREATE_PUBLIC_THREADS | Permissions.CREATE_PRIVATE_THREADS | 
                                Permissions.MANAGE_THREADS)) -> None:
        
        self.max = max
        self.message = message
        
        self.embed = Embed(
            title = 'Select Channel(s)',
            description = f'{(await client.rest.fetch_my_user()).mention} requires the following permissions: ```{reqPerms.__str__().replace("|", ", ")}```',
            color = Color(0xf3df73)
        )
        
        try:
            cachedChannels = await client.rest.fetch_guild_channels(guild)
        except:
            logger.error(sys.exc_info())
        
        textChnls = []
        for val in cachedChannels:
            val: GuildChannel = val
            if val.type.value == 0:
                if HasChannelPermission(val, guild, guild.get_my_member(), reqPerms):
                    textChnls.append({"valid":True, "channel":val})
                elif HasChannelPermission(val, guild, guild.get_my_member(), Permissions.SEND_MESSAGES | Permissions.VIEW_CHANNEL):#MANAGE_THREADS
                    for perm in reqPerms:
                        if not HasChannelPermission(val, guild, guild.get_my_member(), perm):
                            textChnls.append({"valid":False, "channel":val, "perm":perm})
                            break

        if len(textChnls) < 1:
            raise NoValues
        
        # Sort channels so favorites appear first
        if fav_channels:
            textChnls.sort(key=lambda x: x["channel"].id not in fav_channels)
        
        split_templates = [
            textChnls[i:i + 20] for i in range(0, len(textChnls), 20)
        ]  # Split the list into chunks of size 20
        
        for i, s in enumerate(split_templates, 0):
            selectMenus = []
            
            if (reqNone or split_templates.__len__() > 1) and i != split_templates.__len__() - 1:
                selectMenus.append(TextSelectOption(label="None" if reqNone else "Next Page ➡️", value="0", emoji=Emoji.parse('<:validchannel:1120728238667346051>')))
            
            for t in s:
                selectMenus.append(TextSelectOption(label=t["channel"].name, 
                                                    value=str(t["channel"].id), 
                                                    description=None if t["valid"] else f'Missing Permission:\n {str(t["perm"].name)}',
                                                    emoji=Emoji.parse('<:validchannel:1120728238667346051>' if t["valid"] else '<:invalidchannel:1120728255633301526>')))
                
            self.selction_stages.append(selectMenus)
        
        
        self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_select,
                                           max_values=self.max if self.selction_stages[self.currentStage].__len__() > self.max else self.selction_stages[self.currentStage].__len__())
        
        self.btn = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.on_cancel,
            label="Cancel",
            #custom_id="cancel_button",
        )
        
        self.btn2 = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.on_refresh,
            label="Refresh",
            #custom_id="refresh_button",
        )
        
        self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
        
        return self
    
    async def on_select(self, ctx: components.MenuContext) -> None:
        if ctx.selected_values_for(self.select)[0] != "0":
            self.selected_channels.extend(ctx.selected_values_for(self.select))
        
        if self.selected_channels.__len__() == self.max or self.currentStage == self.selction_stages.__len__() - 1:
            ctx.stop_interacting()
            return
        else:
            self.currentStage += 1
            
            try:
                self.select.max_values = self.max - self.selected_channels.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__()
                self.select.options = self.selction_stages[self.currentStage]
            except IndexError:
                print(f"No more pages {self.selction_stages.__len__()}")
                ctx.stop_interacting()
                return
            
            self.embed.set_footer(f'Part {self.currentStage+1}/{len(self.selction_stages)}')
            await self.message.edit(self.embed, components=self)
            
            await ctx.defer(edit=True)
    
    async def on_cancel(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        self.cancel_setup = True
        ctx.stop_interacting()
            
    async def on_refresh(self, ctx: components.MenuContext) -> None:
        self.previous_row()
        self.clear_current_row()
        
        try:
            self.select = self.add_text_select(self.selction_stages[self.currentStage], self.on_refresh,
                                                max_values=self.max - self.selected_channels.__len__() if self.selction_stages[self.currentStage].__len__() > self.max - self.selected_channels.__len__() else self.selction_stages[self.currentStage].__len__())
        except IndexError:
            await ctx.defer(edit=True)
            ctx.stop_interacting()
        
        await self.message.edit(self.embed, components=self)