import sys
import asyncio

from asgiref.sync import sync_to_async

from hikari import Embed, Permissions, Color, GuildChannel
from hikari.applications import ApplicationContextType as ApplicationContextType

import lightbulb

from cache.helpers import save_discord_meta_models

from app.models import Config

from bot.bot.utils.exceptions import SetupCancel
from bot.bot.components.support_button import SupportButton
from bot.bot.utils.config_utils import RunConfigBuilder
from bot.bot.utils.util import DBifyReminder


from loguru import logger

embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the modal timedout.',
    color = Color(0xff0000)
)

loader = lightbulb.Loader()


@loader.command()#guilds=[MAIN_GUILD_ID, 781645306689093642])
class ConfigCommand(
    lightbulb.SlashCommand,
    name="extensions.config.name",
    description="extensions.config.description",
    default_member_permissions=Permissions.ADMINISTRATOR,
    localize=True,
    contexts=[ApplicationContextType.GUILD]
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"ConfigCommand: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        logChnl, channels, autocleanT = None, None, None
        
        rsp_snowflake = None
        try:
            rsp_snowflake = await ctx.respond(content=Embed(title='Loading Server Setup...'), ephemeral=True)
        except Exception as e:
            await ctx.respond(content=Embed(title='Error contact support!'), ephemeral=True, components=SupportButton())
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        guild = ctx.interaction.get_guild()

        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.warning(f'Guild {guild.name}:{guild.id} did not have a config, creating one')
            config = await sync_to_async(Config.objects.create)(guild=int(guild.id))
        
        
        logChnl = config.log_channel
        
        channels = config.event_channels
        
        thread_delete_method = config.thread_delete_method
        
        checkinTM = config.checkin_time
        autocleanT = config.autoclean
        
        
        ################################
        # Config Builder
        ################################
        try:
            config = await RunConfigBuilder(ctx, client, rsp_snowflake, config)
        except (asyncio.TimeoutError, SetupCancel): #These are handled in the RunConfigBuilder
            return
        except:
            logger.error(sys.exc_info())
            return
                    
        # Guild Logs
        if config.log_channel != 0 and config.log_channel is not None:
            logs: list = []
            if config.log_channel != logChnl and config.log_channel != 0:
                logs.append(f'{ctx.interaction.member.mention} edited Log Channel changed from <#{config.log_channel}> to <#{logChnl}>')
            elif config.log_channel != logChnl and config.log_channel == 0:
                logs.append(f'{ctx.interaction.member.mention} disabled logging')
            
            if config.thread_delete_method != thread_delete_method:
                logs.append(f'{ctx.interaction.member.mention} edited the Thread Delete Method to {"`Archive`" if config.thread_delete_method == 1 else "`Delete`"}')
            
            if config.event_channels != channels:
                logs.append(f'{ctx.interaction.member.mention} edited the Fav Channels')
                
            if config.checkin_t != DBifyReminder(checkinTM) and config.is_premium:
                logs.append(f'{ctx.interaction.member.mention} edited the Event Check-In time from {config.checkin_t} to {DBifyReminder(checkinTM)}')
            
            if config.autoclean_t != DBifyReminder(autocleanT):
                logs.append(f'{ctx.interaction.member.mention} edited the Event Auto-Clean time from {config.autoclean_t} to {DBifyReminder(autocleanT)}')
        
            logEmbds: list = []
            for log in logs:
                logEmbds.append(Embed(description=log))
            
            if logEmbds.__len__() > 0:
                try:
                    await (await config.log(guild)).send(embeds=logEmbds)
                except Exception as e:
                    logger.error(e)
            
        await ctx.edit_response(rsp_snowflake, Embed(
                title = 'Finished editing the server Config.',
                color = Color(0x00ff00)
            ), components=None)
            