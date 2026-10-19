from hikari import Permissions, Embed
from hikari.applications import ApplicationContextType as ApplicationContextType
import lightbulb

from cache.helpers import save_discord_meta_models

from loguru import logger


loader = lightbulb.Loader()

group = lightbulb.Group(
    name="extensions.cache.name",
    description="extensions.cache.description",
    default_member_permissions=Permissions.ADMINISTRATOR,
    contexts=[ApplicationContextType.GUILD],
    localize=True
)

loader.command(group, guilds=[MAIN_GUILD_ID])

@group.register
class CacheUpdate(
    lightbulb.SlashCommand,
    name="extensions.cache_update.name",
    description="extensions.cache_update.description",
    localize=True,
):
    guild_id = lightbulb.string("guild_id", "The Guild to update the cache off.", default=None)
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        msg_snow = await ctx.respond(content=Embed(title="Cache Update Started",
                                        description=f"Processing guilds...",
                                        color=0x00ff00))
        
        if self.guild_id is not None:
            try:
                guild = await client.rest.fetch_guild(self.guild_id)
                
                roles = await client.rest.fetch_roles(guild)
                channels = await client.rest.fetch_guild_channels(guild)
            
                await save_discord_meta_models(guild)
                
                for role in roles:
                    await save_discord_meta_models(role, guild)
                for channel in channels:
                    await save_discord_meta_models(channel, guild)
            except:
                await ctx.edit_response(msg_snow, content=Embed(title="Cache Update Failed",
                                            description=f"The cache has failed to update for id `{self.guild_id}`",
                                                color=0xff0000))
            else:
                await ctx.edit_response(msg_snow, content=Embed(title="Cache Updated", 
                                                description=f"The cache has been updated for [{guild.name}](https://discord.com/channels/MAIN_GUILD_ID/928620397589581824{guild.id})",
                                                color=0x00ff00))
            
        else:
            guilds = await client.rest.fetch_my_guilds()
            
            failedGuilds = []
            successGuilds = []
            
            
            for guild in guilds:
                try:
                    guild = await client.rest.fetch_guild(guild.id)
                    await save_discord_meta_models(guild)
                    
                    roles = await client.rest.fetch_roles(guild)
                    channels = await client.rest.fetch_guild_channels(guild)
                
                    for role in roles:
                        await save_discord_meta_models(role, guild)
                    for channel in channels:
                        await save_discord_meta_models(channel, guild)
                except:
                    failedGuilds.append(f'[{guild.name}](https://discord.com/channels/MAIN_GUILD_ID/928620397589581824 "{guild.id}")')
                    continue
                else:
                    successGuilds.append(f'[{guild.name}](https://discord.com/channels/MAIN_GUILD_ID/928620397589581824 "{guild.id}")')
            
            await ctx.edit_response(msg_snow, content=Embed(title="Cache Updated", description=f"The cache has been updated for {', '.join(successGuilds)} "
                                    f"and failed to update for {', '.join(failedGuilds)}", 
                                    color=0x00ff00))
        
        await save_discord_meta_models(ctx)
