import sys
import arrow
import uuid
import asyncio

from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import Snowflakeish, Embed, Permissions, ButtonStyle, Color, Role, ResponseType, MessageFlag

from app.models import Config, Templates, Option_Presets

from bot.bot.modals import TimeModal
from bot.bot.utils.exceptions import NoValues, SetupCancel
from bot.bot.utils.discord_utils import GetChannels, GetBool
from bot.bot.utils.util import HumanizeReminder, DBifyReminder
from bot.bot.components.support_button import SupportButton

from loguru import logger

embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the modal timedout.',
    color = Color(0xff0000)
)

class ConfigBuilder(components.Menu):
    timeout = 60*5
    
    config: Config
    
    embed: Embed
    
    mainSnowflake: Snowflakeish
    mainContext: Context
    
    cancel_setup: bool = False
    
    
    
    def __init__(self, snowflake: Snowflakeish, config: Config):
        self.config = config
        self.mainSnowflake = snowflake
        
        self.log_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_log_channel,
            label="Set Log Channel",
            disabled=self.config.log_channel == 0
        )
        
        self.fav_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_fav_channels,
            label="Set Fav Channels"
        )
        
        self.thread_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_thread_delete_method,
            label="Thread Delete Method"
        )
        
        self.signup_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_signup_overflow_method,
            label="Signup Overflow Method"
        )
        self.next_row()
        
        if self.config.is_premium:
            self.checkin_button = self.add_interactive_button(
                ButtonStyle.PRIMARY,
                self.set_checkin_time,
                label="Set Event Checkin Time"
            )
            
            self.cleanup_button = self.add_interactive_button(
                ButtonStyle.PRIMARY,
                self.set_cleanup_time,
                label="Set Event Cleanup Time",
                disabled=not self.config.is_premium
            )
        
        self.calendar_button = self.add_interactive_button(
            ButtonStyle.SUCCESS if config.calendar_enabled else ButtonStyle.DANGER,
            self.set_calendar_enabled,
            label=f"{'Enable' if not self.config.calendar_enabled else 'Disable'} Calendar"
        )
        self.next_row()
        
        
        self.cancel_button = self.add_interactive_button(
            ButtonStyle.SUCCESS,
            self.finish,
            label="Finish"
        )
        
        self.cancel_button = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.cancel,
            label="Cancel"
        )
        
        if not self.config.is_premium:
            self.cancel_button = self.add_link_button(
                "https://baast.app/pricing/",
                label="Get Premium"
            )
     
    
    async def create(self, ctx: Context) -> None:
        self.mainContext = ctx
        self.newFeed = False
        
        self.embed = Embed(
            title = "Config",
            #description = description,
            color = Color(0xf3df73)
        )
        
        chnlsString = ""
        if self.config.event_channels:
            for i, channel in enumerate(self.config.event_channels):
                if i != 0:
                    chnlsString += ", "
                chnlsString += f"<#{channel}>"
        else:
            chnlsString = "None"
        self.embed.add_field("Favorite Channels", chnlsString)
        
        self.embed.add_field("Log Channel", f"<#{self.config.log_channel}>" if self.config.logs_enabled else "Disabled", inline=True)
        
        self.embed.add_field("Thread Delete Method", "Delete" if self.config.thread_delete_method == 0 else "Archive")
        
        self.embed.add_field("Signup Overflow Method", "Truncate" if self.config.signup_overflow_method == 0 else "Overflow")
        
        self.embed.add_field("Calendar Enabled", "Enabled" if self.config.calendar_enabled else "Disabled")
        
        if self.config.is_premium:
            self.embed.add_field("Checkin Time", f"`{HumanizeReminder(self.config.checkin_time)}`")
            self.embed.add_field("Auto Clean", f"`{HumanizeReminder(self.config.autoclean)}`")
        
        
        return self
    
    
    async def set_log_channel(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        
        try:
            channel = await GetChannels(self.mainContext, ctx.client, self.mainSnowflake, max=1, 
                                        title="Select a Log Channel",
                                        reqPerms=(Permissions.SEND_MESSAGES | Permissions.VIEW_CHANNEL | Permissions.MANAGE_WEBHOOKS))
        except NoValues:
            await ctx.respond(content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `SEND_MESSAGES`, `SEND_MESSAGES_IN_THREADS`, `VIEW_CHANNEL`, `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, `MANAGE_THREADS`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
            return
        except:
            logger.error(sys.exc_info())
            return
        
        self.config.log_channel = int(channel[0])
        
        self.embed.edit_field(1, "Log Channel", f"<#{self.config.log_channel}>" if self.config.logs_enabled else "Disabled", inline=True)
        
        self.newFeed = await GetBool(self.mainContext, ctx.client, self.mainSnowflake, description="Enable Baast news feed for the log channel?")
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        
        ctx.set_timeout(self.timeout)
        
    async def set_fav_channels(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        
        try:
            channels = await GetChannels(self.mainContext, ctx.client, self.mainSnowflake, max=10)
        except NoValues:
            await ctx.respond(content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `SEND_MESSAGES`, `SEND_MESSAGES_IN_THREADS`, `VIEW_CHANNEL`, `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, `MANAGE_THREADS`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
            return
        except SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        self.config.event_channels = channels
        
        chnlsString = ""
        if self.config.event_channels:
            for i, channel in enumerate(self.config.event_channels):
                if i != 0:
                    chnlsString += ", "
                chnlsString += f"<#{channel}>"
        else:
            chnlsString = "None"
        self.embed.edit_field(0, "Favorite Channels", chnlsString, inline=True)
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        
        ctx.set_timeout(self.timeout)
        
    async def set_thread_delete_method(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        
        try:
            deleteMethod = await GetBool(self.mainContext, ctx.client, self.mainSnowflake, title="Thread Delete Method", 
                                        description="Choose how to delete the event thread.", no="Delete", yes="Archive")
        except:
            logger.error(sys.exc_info())
            return
        
        self.config.thread_delete_method = deleteMethod
        self.embed.edit_field(2, "Thread Delete Method", "Delete" if self.config.thread_delete_method == 0 else "Archive")
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        
        ctx.set_timeout(self.timeout)
    
    async def set_checkin_time(self, ctx: components.MenuContext) -> None:
        modal = TimeModal(time=self.config.checkin_time)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the Checkin time.", custom_id=c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id, timeout=120)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
            pass
        else:
            self.config.checkin_t = DBifyReminder(modal.value)
            self.embed.edit_field(5, "Checkin Time", f"`{HumanizeReminder(self.config.checkin_time)}`")
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
        
        ctx.set_timeout(self.timeout)
    
    async def set_cleanup_time(self, ctx: components.MenuContext) -> None:
        modal = TimeModal(time=self.config.autoclean)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the Event cleanup time.", custom_id=c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id, timeout=120)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
            pass
        else:
            self.config.autoclean_t = DBifyReminder(modal.value)
            self.embed.edit_field(6, "Auto Clean", f"`{HumanizeReminder(self.config.autoclean)}`")
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
        
        ctx.set_timeout(self.timeout)
        
    async def set_signup_overflow_method(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        
        try:
            overflowMethod = await GetBool(self.mainContext, ctx.client, self.mainSnowflake, title="Signup Overflow Method", 
                                        description="Choose how to handle signup overflow.", no="Truncate", yes="Overflow")
        except:
            logger.error(sys.exc_info())
            return
        
        self.config.signup_overflow_method = overflowMethod
        self.embed.edit_field(3, "Signup Overflow Method", "Truncate" if self.config.thread_delete_method == 0 else "Overflow")
        
        await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        
        ctx.set_timeout(self.timeout)
        
    async def set_calendar_enabled(self, ctx: components.MenuContext) -> None:
        await ctx.defer(edit=True)
        
        try:
            self.config.calendar_enabled = not self.config.calendar_enabled
            self.calendar_button.style = ButtonStyle.SUCCESS if self.config.calendar_enabled else ButtonStyle.DANGER
            self.calendar_button.label = f"{'Enable' if self.config.calendar_enabled else 'Disable'} Calendar"
            
            self.embed.edit_field(4, "Calendar Enabled", "Enabled" if self.config.calendar_enabled else "Disabled")
            
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        except:
            logger.error(sys.exc_info())
            return
    
    
    ## End Buttons Functions
    async def finish(self, ctx: components.MenuContext) -> tuple[dict, arrow.Arrow, list[Role]]:
        self.disable_all_components()
        
        await self.config.asave()
        
        await self.mainContext.edit_response(self.mainSnowflake, Embed(
            title = None,
            description = 'You finished creating an event.',
            color = Color(0x55ff55)
        ), components=None)
        
        ctx.stop_interacting()
    
    async def cancel(self, ctx: components.MenuContext) -> None:
        self.disable_all_components()
        
        await self.mainContext.edit_response(self.mainSnowflake, 
                                             Embed(description="Config Editing Canceled.", color=Color(0xff5555)), 
                                             components=None)
        
        self.cancel_setup = True
        ctx.stop_interacting()
