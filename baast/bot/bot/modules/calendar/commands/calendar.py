import sys

from asgiref.sync import sync_to_async

from hikari import Embed, Permissions, Color
from hikari.applications import ApplicationContextType as ApplicationContextType
from hikari.impl import MessageActionRowBuilder
import lightbulb

from cache.helpers import save_discord_meta_models

from app.models import Config

from bot.bot.modules.events.classes.calendar import Calendar

from loguru import logger

loader = lightbulb.Loader()

group = lightbulb.Group(
    name="extensions.calendar.name",
    description="extensions.calendar.description",
    default_member_permissions=Permissions.ADMINISTRATOR,
    contexts={ApplicationContextType.GUILD},
    localize=True
)

loader.command(group)#, guilds=[MAIN_GUILD_ID, 781645306689093642])

@group.register
class CalendarEnable(
    lightbulb.SlashCommand,
    name="extensions.calendar_enable.name",
    description="extensions.calendar_enable.description",
    localize=True,
):
    state = lightbulb.boolean("toggle", "Enable/Disable Google calendar integration for this server.")
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Command to enable/disable calendar."""
        logger.info(f"CalendarEnable: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild = ctx.interaction.get_guild()
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.respond(Embed(description="Error: Guild has not Config..."), ephemeral=True)
            return
        except:
            logger.error(sys.exc_info())
            ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        else:
            if self.state:
                config.calendar_enabled = True
                
                if config.is_premium:
                    try:
                        cal: Calendar = Calendar()
                    except:
                        logger.error(sys.exc_info())
                    else:
                        if config.calendar_id == None or not cal.check_calendar_exists(config.calendar_id):
                            try:
                                await sync_to_async(cal.create_calendar)(guild, config)
                            except:
                                logger.error(sys.exc_info())
                
            else:
                config.calendar_enabled = False
            
            await config.asave()
            
            extra_text = ""
            if not config.is_premium and config.calendar_enabled:
                extra_text = ("*This guild is not premium, so the calendar support is limited to a lin in the embed for users to manually add the event to their calendar."
                            "Premium guilds have an automated calendar with users only having to add the calendar to their google calendar and the rest is automated.*")
                
            ButtonRow = MessageActionRowBuilder()
            if not config.is_premium:
                ButtonRow.add_link_button("https://baast.app/pricing/", label="Subscribe")
            else:
                ButtonRow.add_link_button(cal.get_calendar_link(config), label="Find your calendar")
                
            await ctx.respond(Embed(description=f"Google Calendar Integration for {guild.name} has been {'Enabled' if config.calendar_enabled else 'Disabled'}.\n{extra_text}"), ephemeral=True,
                            components=[ButtonRow])
            

@group.register
class CalendarLink(
    lightbulb.SlashCommand,
    name="extensions.calendar_link.name",
    description="extensions.calendar_link.description",
    localize=True,
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Command to give the calendar link."""
        logger.info(f"CalendarLink: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild = ctx.interaction.get_guild()

        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            await ctx.respond(Embed(description="Error: Guild has not Config..."), ephemeral=True)
            return
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        
        try:
            cal: Calendar = Calendar()
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured"), ephemeral=True)
        else:
            if cal.check_calendar_exists(config):
                await ctx.respond(Embed(description=f"[Google Calendar Link]({cal.get_calendar_link(config)})"), ephemeral=True)

@group.register
class CalendarPermission(
    lightbulb.SlashCommand,
    name="extensions.calendar_permission.name",
    description="extensions.calendar_permission.description",
    localize=True,
):
    email = lightbulb.string("email", "The email for the google account to add/edit to the calendar.")
    permmission = lightbulb.string("perm", "The permission this email should have.", 
                                   choices=[lightbulb.Choice("extensions.calendar_permission.option.permission.reader", "reader", localize=True), 
                                            lightbulb.Choice("extensions.calendar_permission.option.permission.writer", "writer", localize=True), 
                                            lightbulb.Choice("extensions.calendar_permission.option.permission.owner", "owner", localize=True)])
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Command to set the permissions of an email for the calendar."""
        logger.info(f"CalendarPermission: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild = ctx.interaction.get_guild()
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            await ctx.respond(Embed(description="Error: Guild has not Config..."), ephemeral=True)
            return
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        
        try:
            cal: Calendar = Calendar()
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        else:
            if config.calendar_id == None or not cal.check_calendar_exists(config.calendar_id):
                try:
                    await sync_to_async(cal.create_calendar)(guild, config)
                except:
                    logger.error(sys.exc_info())
                    await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
                    return
            
            try:
                cal.add_access_to_calendar(config, self.email, self.permmission)
            except:
                logger.error(sys.exc_info())
                await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
                return
            
            await ctx.respond(Embed(description=f"[Google Calendar Link]({cal.get_calendar_link(config)})"), ephemeral=True)


@group.register
class CalendarPrivate(
    lightbulb.SlashCommand,
    name="extensions.calendar_private.name",
    description="extensions.calendar_private.description",
    localize=True,
):
    private = lightbulb.boolean("private", "Set the calendar to private.")
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Command to set the permissions of an email for the calendar."""
        logger.info(f"CalendarPrivate: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild = ctx.interaction.get_guild()
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            await ctx.respond(Embed(description="Error: Guild has not Config..."), ephemeral=True)
            return
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        
        try:
            cal: Calendar = Calendar()
        except:
            logger.error(sys.exc_info())
            await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
            return
        else:
            if cal.check_calendar_exists(config):
                try:
                    cal.update_public_access_rule(config, role="reader" if not self.private else "None")
                except:
                    logger.error(sys.exc_info())
                    await ctx.respond(Embed(description="An Error Occured..."), ephemeral=True)
                    return
                
                await ctx.respond(Embed(description=f"The calendar is now set as {'Private' if self.private else 'Public'} - [Google Calendar Link]({cal.get_calendar_link(config)})"), ephemeral=True)