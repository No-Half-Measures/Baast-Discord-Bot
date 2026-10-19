from asgiref.sync import sync_to_async

from hikari import ButtonStyle, MessageFlag
import lightbulb

from app.models import Config

async def _has_config_setup(ctx: lightbulb.Context):
    guild = ctx.get_guild()
    config = await sync_to_async(Config.objects.get)(guild=int(guild.id))

    if config:
        return True

    await ctx.respond("You need to run `/config` and complete befor you are able to run any event command.")
    return False
has_config_setup = lightbulb.Check(_has_config_setup)

async def _is_premium(ctx: lightbulb.Context):
    guild = ctx.get_guild()
    config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
    
    if config.is_premium:
        return True
    
    upgrade_button = ctx.app.rest.build_message_action_row().add_link_button("https://baast.app/pricing/", label='Upgrade')

    await ctx.respond("This Command is a Premium Feature.", component=upgrade_button, flags=MessageFlag.EPHEMERAL)
    return False
is_premium = lightbulb.Check(_is_premium)