import lightbulb
from hikari import SpacingType, MessageFlag
from hikari.applications import ApplicationContextType as ApplicationContextType
from hikari.impl import ContainerComponentBuilder, TextDisplayComponentBuilder, SeparatorComponentBuilder, MessageActionRowBuilder, LinkButtonBuilder

from cache.helpers import save_discord_meta_models

from bot.bot.components.help_components import HelpComponents

from loguru import logger

loader = lightbulb.Loader()

@loader.command()#guilds=[MAIN_GUILD_ID, 781645306689093642])
class Help(
    lightbulb.SlashCommand,
    name="extensions.help.name",
    description="extensions.help.description",
    localize=True,
    contexts={ApplicationContextType.GUILD},
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"Help: {ctx.interaction.guild_id}")
        
        await save_discord_meta_models(ctx)
        
        components = HelpComponents
        
        await ctx.respond(components=components, ephemeral=True, flags=MessageFlag.IS_COMPONENTS_V2)
