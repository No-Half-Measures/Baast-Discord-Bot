from datetime import datetime
import sys

from asgiref.sync import sync_to_async

from hikari import Embed, Color
from hikari.applications import ApplicationContextType as ApplicationContextType
import lightbulb

from cache.helpers import save_discord_meta_models

from discord.models import User

from loguru import logger


loader = lightbulb.Loader()

@loader.command()#guilds=[MAIN_GUILD_ID, 781645306689093642])
class Reminder(
    lightbulb.SlashCommand,
    name="extensions.reminder.name",
    description="extensions.reminder.description",
    localize=True,
    contexts=[ApplicationContextType.GUILD],
):
    state = lightbulb.boolean("toggle", "Enable or Disable event reminders.", default=True)
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"Reminder: {ctx.user.id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        user, created = await sync_to_async(User.objects.get_or_create)(id=ctx.user.id, defaults={
            'avatar': ctx.user.avatar_hash if ctx.user.avatar_hash != None else 'none',
            'public_flags': ctx.user.flags,
            'flags': ctx.user.flags,
            'locale': 'en-US',
            'mfa_enabled': False,
            'discord_tag': f'{ctx.user.username}',
            'last_login': datetime.now()
        })
            
        user.notifications_enabled = self.state
        try:
            await user.asave()
        except:
            logger.error(sys.exc_info()[0])
        else:
            embed = Embed(description=f"Turned {'On' if self.state else 'Off'} event reminders for you.", color=Color(0x5EB000) if self.state else Color(0xB00020))
            await ctx.respond(content=embed, ephemeral=True)