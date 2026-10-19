from asgiref.sync import sync_to_async

from hikari import Embed, Permissions, Color
from hikari.applications import ApplicationContextType as ApplicationContextType
import lightbulb

from cache.helpers import save_discord_meta_models

from discord.models import User


from loguru import logger

loader = lightbulb.Loader()

group = lightbulb.Group(
    name="extensions.user.name",
    description="extensions.user.description",
    default_member_permissions=Permissions.ADMINISTRATOR,
    contexts=[ApplicationContextType.GUILD],
    localize=True
)

loader.command(group)#, guilds=[MAIN_GUILD_ID, 781645306689093642])

@group.register
class UserInfo(
    lightbulb.SlashCommand,
    name="extensions.user_info.name",
    description="extensions.user_info.description",
    localize=True,
):
    user = lightbulb.user("user", "The user to get the info of.")
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f"UserInfo: {ctx.interaction.guild_id}")
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild = await client.rest.fetch_guild(ctx.guild_id)
        member = guild.get_member(self.user)
        
        try:
            user: User = await sync_to_async(User.objects.get)(id=member.id)
        except User.DoesNotExist:
            logger.warning(f"Member {member.id} not found in User Tabel.")
        else:
            userEmbed = Embed(
                color = member.accent_color if member.accent_color != None else Color(0x5EB000),
                title = member.nickname,
                )
            userEmbed.set_thumbnail(member.avatar_url)
            userEmbed.add_field('User:', member.username, inline=True)
            userEmbed.add_field('ID:', member.id, inline=True)
            userEmbed.add_field('Joined the Guild on', f'<t:{int(member.joined_at.timestamp())}:F>', inline=False)
            userEmbed.add_field('Account Created', f'<t:{int(member.created_at.timestamp())}:R> \n', inline=False)
            
            userEmbed.add_field('Notifications:', 'Enabled' if user.notifications_enabled == True else 'Disabled', inline=False)
            
            
            # temp = user.memberof
            # guildStr = ''
            
            # if temp != None:
            #     guildList = json.loads(temp)
            #     for gs in guildList:
            #         gill = ctx.bot.cache.get_guild(int(gs))
            #         guildStr += f'{gill.name}\n'
            # else:
            #     guildStr = '`None`'

            # userEmbed.add_field('Member of:', guildStr, inline=False)

            await ctx.respond(content=userEmbed)