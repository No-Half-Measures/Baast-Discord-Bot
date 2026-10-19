from hikari.applications import ApplicationContextType as ApplicationContextType
from hikari import EntitlementOwnerType
from hikari import MessageFlag

import lightbulb

from loguru import logger

from bot.bot.components.help_components import WelcomeComponents

loader = lightbulb.Loader()

@loader.command(guilds=[MAIN_GUILD_ID])
class Help(
    lightbulb.SlashCommand,
    name="test_subscribe",
    description="Test the subscribe listener",
    localize=False,
    contexts={ApplicationContextType.GUILD},
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        #await ctx.client.rest.create_test_entitlement(839928249085722634, sku=1392892692543045815, owner_id=ctx.guild_id, owner_type=EntitlementOwnerType.GUILD)
        #await ctx.respond("Tested")

        await ctx.respond(components=WelcomeComponents, ephemeral=True, flags=MessageFlag.IS_COMPONENTS_V2)