import re
import sys
import asyncio
import arrow
import uuid

from hikari.files import ensure_resource
from lightbulb import components, Context
from lightbulb.components import TextSelectOption
from hikari import Resourceish, Snowflakeish, Embed, Permissions, ButtonStyle, GuildChannel, Emoji, Color, User, Role, MessageFlag, ComponentInteraction
from hikari.impl import ContainerComponentBuilder, TextDisplayComponentBuilder, MessageActionRowBuilder, LinkButtonBuilder

from app.models import Config, Events, Templates, Option_Presets

from bot.bot.modals import TitleDescriptionModal, RecurringModal, DateModal, ImageModal, ColorModal, CapacityModal
from bot.bot.utils.exceptions import SetupCancel
from bot.bot.utils.discord_utils import GetRoles, roles_to_string, GetBool

from loguru import logger

embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the command timedout.',
    color = Color(0xff0000)
)

premium_components = [
    ContainerComponentBuilder(
        components=[
            TextDisplayComponentBuilder(content="This guild has reached the maximum number of recurring events.\nTo post more recurring events, please upgrade to premium."),
            MessageActionRowBuilder(
                components=[
                    LinkButtonBuilder(
                        url="https://baast.app/pricing",
                        label="Premium",
                    ),
                ]
            ),
        ]
    ),
]

class EventBuilder(components.Menu):
    timeout = 60*5
    
    template: Templates
    option_preset: Option_Presets
    
    mentions: list[Role]
    
    title: str
    description: str | None
    capacity: int
    color: str
    date: arrow.Arrow
    thumbnail: str
    author: User
    
    embed: Embed
    
    recurring_interval: int
    recurring_until: arrow.Arrow
    keep_signup_data: bool
    
    mainSnowflake: Snowflakeish
    mainContext: Context | ComponentInteraction
    
    cancel_setup: bool = False
    
    def __init__(self, snowflake: Snowflakeish, template: Templates, preset: Option_Presets):
        self.template = template
        self.option_preset = preset
        self.mainSnowflake = snowflake
        
        
        self.title_desc_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_title_description,
            label="Set Title & Description"
        )
        
        self.date_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_date,
            label="Set Date"
        )
        
        self.recurring_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_recurring,
            label="Set as Repeating"
        )
         
        self.keep_signup_data_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_keep_signup_data,
            label="Keep Signup Data",
            disabled=True
        )
        
        self.next_row()
        
        
        if preset.use_capacity:
            self.capacity_button = self.add_interactive_button(
                ButtonStyle.PRIMARY,
                self.set_capacity,
                label="Set Capacity"
            )
        
        self.thumbnail_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_thumbnail,
            label="Set Thumbnail"
        )
        
        self.color_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_color,
            label="Set Color"
        )
        
        self.mentions_button = self.add_interactive_button(
            ButtonStyle.PRIMARY,
            self.set_mentions,
            label="Mention Roles"
        )
        self.next_row()
        
        
        self.finish_button = self.add_interactive_button(
            ButtonStyle.SUCCESS,
            self.finish,
            label="Finish"
        )
        
        self.cancel_button = self.add_interactive_button(
            ButtonStyle.DANGER,
            self.cancel,
            label="Cancel"
        )
     
    
    async def create(self, ctx: Context | ComponentInteraction, author: User,
                    title: str = None, description: str = None, capacity: int = 100, 
                    thumb: str = None, dateTime: arrow.Arrow = arrow.utcnow(), color: str = '#f3df73',
                    recurring_interval: int = 0, recurring_until: arrow.Arrow = None, 
                    keep_signup_data: bool = False, reccuring_events_count: int = 0) -> None:
        self.mainContext = ctx
        
        self.title = title
        self.description = description
        self.capacity = capacity
        self.thumbnail = thumb
        self.date = dateTime
        self.color = color
        
        self.recurring_interval = recurring_interval
        self.recurring_until = recurring_until
        self.keep_signup_data = keep_signup_data
        
        self.author = author
        self.mentions = []
        
        self.current_recurring = reccuring_events_count
        self.max_recurring = 2
        
        self.keep_signup_data_button.disabled = False if self.recurring_interval > 0 else True
        
        if self.keep_signup_data:
            self.keep_signup_data_button.style = ButtonStyle.SUCCESS
        else:
            self.keep_signup_data_button.style = ButtonStyle.DANGER
        
        
        self.embed = Embed(
            title = self.title if self.title != None else "New Event (Please enter a title!)",
            description = self.description,
            color = Color.of(color)
        )
        
        
        try:
            self.embed.add_field(name='Date', value=self.date_string(), inline=False )
        except Exception as e:
            logger.error(e)
            
        
        for i, option in enumerate(self.option_preset.options):
            if self.option_preset.name == "Default" and i == 0:
                if capacity == None:
                    self.embed.add_field(name=option['label'], value='None', inline=True )
                else:
                    self.embed.add_field(name=f'{option["label"]}  0/{str(capacity)}', value='None', inline=True )
            else:
                self.embed.add_field(name=option['label'], value='None', inline=True )
        
        if not self.template:
            self.embed.set_footer(text=f"Created by {author.username}")
        else:
            if self.template.name == "Default":
                self.embed.set_footer(text=f"Created by {author.username}")
            else:
                try:
                    self.embed.set_footer(text=f"{self.template.name} | Created by {author.username}", icon=self.template.thumb)
                except Exception as e:
                    logger.error(f"Failed to set footer: {e}")
                    self.embed.set_footer(text=f"{self.template.name} | Created by {author.username}")
            
        self.embed.timestamp = arrow.utcnow().datetime

        if thumb:
            self.embed.set_image(thumb)

        return self
        
    async def set_title_description(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        modal = TitleDescriptionModal(title=self.title, description=self.description)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the events title and description.", custom_id=c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id, timeout=300)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
            
        self.title = modal.title
        self.description = modal.description
        
        self.embed.title = self.title
        self.embed.description = self.description
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=self.embed)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
            
        ctx.set_timeout(self.timeout)
    
    async def set_date(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        modal = DateModal(date=self.date)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the events date.", c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
        except ValueError:
            ctx.set_timeout(self.timeout)
            return
        else:
            self.date = modal.value
            
        self.embed.edit_field(0, "Date", self.date_string())
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=self.embed)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
            
        ctx.set_timeout(self.timeout)
    
    async def set_recurring(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        if self.current_recurring >= self.max_recurring:
            await ctx.respond(components=premium_components, flags=MessageFlag.EPHEMERAL | MessageFlag.IS_COMPONENTS_V2, ephemeral=True)
        else:
            modal = RecurringModal(date=self.recurring_until, interval=self.recurring_interval, allow_none=True, require_time=False)
            c_id: str = str(uuid.uuid4())
            
            await ctx.respond_with_modal("Set the date this event will end recurring.", c_id, components=modal)
            try:
                await modal.attach(ctx.client, c_id)
            except asyncio.TimeoutError:
                await ctx.respond(embedTimeout, ephemeral=True)
            else:
                self.recurring_until = modal.recurring_until
                self.recurring_interval = modal.interval
                
                self.keep_signup_data_button.disabled = False if self.recurring_interval > 0 else True
                    
            
            self.embed.edit_field(0, 'Date', self.date_string())
            
            if type(self.mainContext) == ComponentInteraction:
                await self.mainContext.edit_initial_response(embed=self.embed)
            else:
                await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
                
        ctx.set_timeout(self.timeout)
    
    async def set_thumbnail(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        modal = ImageModal(img_url=self.thumbnail)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the events thumbnail.", c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
        
        try:
            resource = ensure_resource(modal.value)
        except Exception as e:
            logger.error(e)
            await ctx.respond(Embed(description="Invalid Thumnail URL."), ephemeral=True)
            ctx.set_timeout(self.timeout)
        else:
            self.thumbnail = modal.value
            self.embed.set_thumbnail(self.thumbnail)
            if type(self.mainContext) == ComponentInteraction:
                await self.mainContext.edit_initial_response(embed=self.embed)
            else:
                await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
                
        ctx.set_timeout(self.timeout)
    
    async def set_color(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        modal = ColorModal(color=self.color)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the events color.", c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
            
        self.color = modal.value
        self.embed.color = Color.of(self.color)
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=self.embed)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
        
        ctx.set_timeout(self.timeout)
    
    async def set_mentions(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        try:
            self.mentions = await GetRoles(self.mainContext, ctx.client, self.mainSnowflake)
        except:
            logger.error(sys.exc_info())
            return
        
        mentionStr, everyone = roles_to_string(self.mentions)
        
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(mentionStr, embed=self.embed, mentions_everyone=everyone, components=self)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, mentionStr, embed=self.embed, mentions_everyone=everyone, components=self)
        
        ctx.set_timeout(self.timeout)
        
    
    async def set_capacity(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        modal = CapacityModal(capacity=self.capacity)
        c_id: str = str(uuid.uuid4())
        
        await ctx.respond_with_modal("Set the events attending capacity.", custom_id=c_id, components=modal)
        try:
            await modal.attach(ctx.client, c_id)
        except asyncio.TimeoutError:
            await ctx.respond(embedTimeout, ephemeral=True)
            
        self.capacity = modal.value
        
        
        for i, option in enumerate(self.option_preset.options, 1):
            if self.option_preset.name == "Default" and i == 1:
                if self.capacity == None:
                    self.embed.edit_field(i, option['label'], 'None', inline=True )
                else:
                    self.embed.edit_field(i, f'{option["label"]}  0/{str(self.capacity)}', 'None', inline=True )
            else:
                self.embed.edit_field(i, option['label'], 'None', inline=True )
        
        
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=self.embed)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed)
        
        ctx.set_timeout(self.timeout)
    
    async def set_keep_signup_data(self, ctx: components.MenuContext) -> None:
        ctx.set_timeout(self.timeout)
        
        try:
            self.keep_signup_data = await GetBool(self.mainContext, ctx.client, self.mainSnowflake, 
                                          title="Keep Signups?",
                                          description="Do you wish for this event to keep signups when it renews?")
        except:
            logger.error(sys.exc_info())
            return
        
        if self.keep_signup_data:
            self.keep_signup_data_button.style = ButtonStyle.SUCCESS
        else:
            self.keep_signup_data_button.style = ButtonStyle.DANGER
        
        if type(self.mainContext) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=self.embed, components=self)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, embed=self.embed, components=self)
        
        ctx.set_timeout(self.timeout)
        
    
    async def finish(self, ctx: components.MenuContext) -> tuple[dict, arrow.Arrow, list[Role]]:
        self.disable_all_components()
        
        try:
            now = arrow.utcnow().shift(minutes=15)
            if self.title == None or self.date <= now:
                await ctx.respond(Embed(
                    title = None,
                    description = f'Title must be set and Date must be greater than `{now.format("DD/MM/YYYY h:mm A ZZZ")}`.',
                    color = Color(0xFFA500)
                ), components=None, flags=MessageFlag.EPHEMERAL)
                
                self.enable_all_components()
                return
            
            if type(self.mainContext) == ComponentInteraction:
                await self.mainContext.edit_initial_response(embed=Embed(
                    title = None,
                    description = 'You finished creating an event.',
                    color = Color(0x55ff55)
                ), components=None)
            else:
                await self.mainContext.edit_response(self.mainSnowflake, Embed(
                    title = None,
                    description = 'You finished creating an event.',
                    color = Color(0x55ff55)
                ), components=None)
        except:
            logger.error(sys.exc_info())
        
        ctx.stop_interacting()
    
    async def cancel(self, ctx: components.MenuContext) -> None:
        self.disable_all_components()
        
        if type(ctx) == ComponentInteraction:
            await self.mainContext.edit_initial_response(embed=Embed(description="You cancelled creating an event.", color=Color(0xff5555)), 
                                                         components=None)
        else:
            await self.mainContext.edit_response(self.mainSnowflake, 
                                             Embed(description="You cancelled creating an event.", color=Color(0xff5555)), 
                                             components=None)
        
        self.cancel_setup = True
        ctx.stop_interacting()
    
    

    def date_string(self) -> str:
        date_value = f"<t:{int(self.date.to('utc').datetime.timestamp())}:F><t:{int(self.date.to('utc').datetime.timestamp())}:R>"
        if self.recurring_interval > 0:
            # Check if the interval is a multiple of 7 (weeks)
            if self.recurring_interval % 7 == 0:
                weeks = self.recurring_interval // 7
                recurrence_text = f"\n**Recurring**: Every {weeks} week{'s' if weeks > 1 else ''}"
            else:
                recurrence_text = f"\n**Recurring**: Every {self.recurring_interval} day{'s' if self.recurring_interval > 1 else ''}"
            
            if self.recurring_until:
                recurrence_text += f" until <t:{int(arrow.get(self.recurring_until).to('utc').datetime.timestamp())}:D>"
                
            date_value += recurrence_text
            
        return date_value
