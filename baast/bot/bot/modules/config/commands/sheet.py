import sys
from asgiref.sync import sync_to_async

import hikari
from hikari import Permissions, Embed, MessageFlag
from hikari.applications import ApplicationContextType as ApplicationContextType

import lightbulb

from cache.helpers import save_discord_meta_models

from app.models import Config
from bot.bot.modules.events.classes.sheet import Sheet



from loguru import logger

loader = lightbulb.Loader()

group = lightbulb.Group(
    name="extensions.sheet.name",
    description="extensions.sheet.description",
    default_member_permissions=Permissions.ADMINISTRATOR,
    contexts=[ApplicationContextType.GUILD],
    localize=True
)

loader.command(group)#, guilds=[MAIN_GUILD_ID, 781645306689093642])


# @group.register
# class SheetCreate(
#     lightbulb.SlashCommand,
#     name="test",
#     description="a test",
#     localize=False
# ):
#     @lightbulb.invoke
#     async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
#         components = [
#                         hikari.impl.ContainerComponentBuilder(
#                             components=[
#                                 hikari.impl.TextDisplayComponentBuilder(content="**# Config**"),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="16964629ddc74e548cd5a23ecb5cfb50",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Favorite Channels**\n#cahnnel #channeltwo"),
#                                     ]
#                                 ),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="10a66988155d4df580613a56df1ac79d",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Log Channel**\n#logChannel"),
#                                     ]
#                                 ),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="60382b8d01c14594c39510f8b4e7b428",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Thread Delete Method**\nDelete"),
#                                     ]
#                                 ),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="87ce740c90984c75a1bd2cd4e739badf",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Signup Overflow Method:**\nTruncate"),
#                                     ]
#                                 ),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="3d53b05f6c0a4f25e1082dfdd2a53cef",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Checkin Time**\n`6 hrs`"),
#                                     ]
#                                 ),
#                                 hikari.impl.SectionComponentBuilder(
#                                     accessory=hikari.impl.InteractiveButtonBuilder(
#                                         style=hikari.components.ButtonStyle.PRIMARY,
#                                         label="Edit",
#                                         custom_id="9bb0d4fa70ea461391c4a43af00d39d8",
#                                     ),
#                                     components=[
#                                         hikari.impl.TextDisplayComponentBuilder(content="**Auto Clean**\n`1 hrs`"),
#                                     ]
#                                 ),
#                             ]
#                         )
#                     ]
        
#         await ctx.respond(components=components, flags=MessageFlag.IS_COMPONENTS_V2)

@group.register
class SheetURL(
    lightbulb.SlashCommand,
    name="extensions.sheet_url.name",
    description="extensions.sheet_url.description",
    localize=True
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"SheetURL: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(ctx.guild_id))
        except Config.DoesNotExist:
            await ctx.respond(embed=Embed(title="Config Not Found", description="This guild does not have a config??? Please contact the bot owner."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        else:
            try:
                sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name)
            except:
                logger.error(sys.exc_info())
                await ctx.respond(embed=Embed(title="Error", description="An error occurred while getting the spreadsheet URLs."), ephemeral=True)
            else:
                try:
                    mainUrl = str(sheets.spreadsheet.url)
                except:
                    logger.error(sys.exc_info())
                    mainUrl = "None"
                    
                try:
                    archiveUrl = str(sheets.archive_spreadsheet.url)
                except:
                    logger.error(sys.exc_info())
                    archiveUrl = "None"
                    
                await ctx.respond(embed=Embed(title="Spreadsheet URLs", description=f"[Live Spreadsheet]({mainUrl})\n[Archive Spreadsheet]({archiveUrl})"), ephemeral=True)

@group.register
class SheetAddUser(
    lightbulb.SlashCommand,
    name="extensions.sheet_adduser.name",
    description="extensions.sheet_adduser.description",
    localize=True
):
    email = lightbulb.string(
        "email",
        "The email of the user to add to the sheet."
    )
    role = lightbulb.string(
        "role",
        "The role of the user to add to the sheet.",
        choices=[
            lightbulb.Choice("extensions.sheet.option.permission.reader", "reader", localize=True),
            lightbulb.Choice("extensions.sheet.option.permission.writer", "writer", localize=True)
        ]
    )
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"SheetAddUser: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(ctx.guild_id))
        except Config.DoesNotExist:
            await ctx.respond(embed=Embed(title="Config Not Found", description="This guild does not have a config??? Please contact the bot owner."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        else:
            try:
                sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name)
            except:
                logger.error(sys.exc_info())
                await ctx.respond(embed=Embed(title="Error", description="An error occurred while adding the user."), ephemeral=True)
            else:
                sheets.addUser(self.email, self.role)
                await ctx.respond(embed=Embed(title="User Added", description=f"User {self.email} has been added to the sheet."), ephemeral=True)

@group.register
class SheetEditUser(
    lightbulb.SlashCommand,
    name="extensions.sheet_edituser.name",
    description="extensions.sheet_edituser.description",
    localize=True
):
    email = lightbulb.string(
        "email",
        "The email of the user to edit on the sheet."
    )
    role = lightbulb.string(
        "role",
        "The role to set the user as.",
        choices=[
            lightbulb.Choice("extensions.sheet.option.permission.reader", "reader", localize=True),
            lightbulb.Choice("extensions.sheet.option.permission.writer", "writer", localize=True)
        ]
    )
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"SheetEditUser: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(ctx.guild_id))
        except Config.DoesNotExist:
            await ctx.respond(embed=Embed(title="Config Not Found", description="This guild does not have a config??? Please contact the bot owner."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        else:
            try:
                sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name)
            except:
                logger.error(sys.exc_info())
                await ctx.respond(embed=Embed(title="Error", description="An error occurred while editing the user."), ephemeral=True)
            else:
                sheets.editUser(self.email, self.role)
                await ctx.respond(embed=Embed(title="User Updated", description=f"User {self.email} has been updated on the sheet."), ephemeral=True)

@group.register
class SheetEditUser(
    lightbulb.SlashCommand,
    name="extensions.sheet_removeuser.name",
    description="extensions.sheet_removeuser.description",
    localize=True
):
    email = lightbulb.string(
        "email",
        "The email of the user to remove from the sheet."
    )
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"SheetRemoveUser: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(ctx.guild_id))
        except Config.DoesNotExist:
            await ctx.respond(embed=Embed(title="Config Not Found", description="This guild does not have a config??? Please contact the bot owner."), ephemeral=True)
            return
        
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.respond(embed=Embed(description=f"This is a premium command which this guild is not of premium status."), 
                                components=[PremiumButtonRow], ephemeral=True)
            return
        else:
            try:
                sheets = Sheet(config, (await client.rest.fetch_guild(ctx.guild_id)).name)
            except:
                logger.error(sys.exc_info())
                await ctx.respond(embed=Embed(title="Error", description="An error occurred while removing the user."), ephemeral=True)
            else:
                sheets.removeUser(self.email)
                await ctx.respond(embed=Embed(title="User Removed", description=f"User {self.email} has been removed from the sheet."), ephemeral=True)