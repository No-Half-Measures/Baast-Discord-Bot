import asyncio, sys

from hikari import (ComponentInteraction, Permissions, Snowflakeish, Embed, Color, Role, User, Message, Guild, OwnGuild,
                    PermissibleGuildChannel, Member, PermissionOverwriteType, GatewayGuild)
from lightbulb import Client, Context

from bot.bot.components import RoleSelect, RoleSelect_M, ChannelSelect, ChannelSelect_M, BooleanButton, GuildSelect
from bot.bot.utils.exceptions import NoValues, SetupCancel

from loguru import logger

embedTimeout = Embed(
    title = None,
    description = 'You took too long to respond thus the command timedout.',
    color = Color(0xff5555)
)

embedCancel = Embed(
    title = None,
    description = 'You cancelled the command.',
    color = Color(0xff5555)
)

async def GetRoles(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, max: int = 20) -> list[Role]:
    try:
        selectObj:RoleSelect = await RoleSelect().create(ctx, snowflake, max=max)
        await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
    except NoValues:
        logger.error(f'No Roles avalible!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(ctx.client, timeout=120)
    except SetupCancel:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    guild = await client.rest.fetch_guild(ctx.guild_id)
    selectedRoles: list[Role] = []
    for id in selectObj.selected_roles:
        selectedRoles.append(guild.get_role(id))
    
    return selectedRoles

async def GetRoles_M(message: Message, guild: Guild, client: Client, max: int = 20) -> list[Role]:
    try:
        selectObj:RoleSelect_M = await RoleSelect_M().create(message, guild, client, max=max)
        await message.edit(selectObj.embed, components=selectObj)
    except NoValues:
        logger.error(f'No Roles avalible!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except SetupCancel:
        await message.edit(embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        await message.edit(embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    selectedRoles: list[Role] = []
    for id in selectObj.selected_roles:
        selectedRoles.append(guild.get_role(id))
    
    return selectedRoles

def roles_to_string(mentions: list) -> tuple[str, bool]:
    mentionStr = ''
    everyone = False
        
    if mentions:
        for m in mentions:
            if m == '@everyone':
                everyone = True
                mentionStr += f'@everyone '
            else:
                mentionStr += f'{m.mention} '

    return mentionStr, everyone

async def GetChannels(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, max: int = 20, 
                      title: str = "Select Channel(s)", description: str = None, fav_channels: list[int] = None, reqNone: bool = True,
                      reqPerms: Permissions = (Permissions.SEND_MESSAGES | Permissions.SEND_MESSAGES_IN_THREADS | Permissions.VIEW_CHANNEL | 
                                               Permissions.CREATE_PUBLIC_THREADS | Permissions.CREATE_PRIVATE_THREADS | Permissions.MANAGE_THREADS)) -> list[int]:
    try:
        selectObj:ChannelSelect = await ChannelSelect().create(ctx, client, snowflake, max=max, reqPerms=reqPerms, fav_channels=fav_channels, reqNone=reqNone)
    except NoValues:
        logger.error(f'Guild {ctx.guild_id} has no accessible channels!')
        raise NoValues
    except:
        logger.error(f'Extra: {sys.exc_info()}')
        return
    else:
        try:
            if isinstance(ctx, ComponentInteraction):
                await ctx.edit_initial_response(embed=selectObj.embed, components=selectObj)
            else:
                await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
        except Exception as e:
            logger.error(f'Error editing response: {e}')
            return

    try:
        await selectObj.attach(client, timeout=120)
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    if selectObj.cancel_setup:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    
    return selectObj.selected_channels

async def GetChannels_M(message: Message, guild: Guild, client: Client, max: int = 20, fav_channels: list[int] = None,
                      reqPerms: Permissions = (Permissions.SEND_MESSAGES | Permissions.SEND_MESSAGES_IN_THREADS | Permissions.VIEW_CHANNEL | 
                                               Permissions.CREATE_PUBLIC_THREADS | Permissions.CREATE_PRIVATE_THREADS | Permissions.MANAGE_THREADS)) -> list[int]:
    try:
        selectObj:ChannelSelect_M = await ChannelSelect_M().create(message, guild, client, max=max, reqPerms=reqPerms, fav_channels=fav_channels)
        await message.edit(selectObj.embed, components=selectObj)
    except NoValues:
        logger.error(f'No Channel Selected!')
        raise NoValues
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except SetupCancel:
        await message.edit(embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        await message.edit(embedTimeout, components=None)
        return
    except:
        logger.error(sys.exc_info())
        return
    
    return selectObj.selected_channels

async def GetBool(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, title:str = None, description:str = None,
                  yes: str = "Yes", no: str = "No") -> bool:
    embed = Embed(
        title = title,
        description = description,
        color = Color(0xf3df73)
    )
    
    try:
        selectObj:BooleanButton = BooleanButton(true_lable=yes, false_label=no)
        
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embed, components=selectObj)
        else:
            await ctx.edit_response(snowflake, embed=embed, components=selectObj)
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(client, timeout=120)
    except SetupCancel:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    return selectObj.value

async def GetGuilds(ctx: Context | ComponentInteraction, client: Client, snowflake: Snowflakeish, 
                    max: int = 1, user: User = None, custom_list: list[OwnGuild] = None, title: str="Select Guild(s)") -> list[Role]:
    try:
        selectObj:GuildSelect = await GuildSelect().create(ctx, snowflake, max=max, user=user, myGuilds=custom_list, title=title)
        await ctx.edit_response(snowflake, embed=selectObj.embed, components=selectObj)
    except NoValues:
        logger.error(f'No Guilds avalible!')
    except:
        logger.error(sys.exc_info())
        return
    
    try:
        await selectObj.attach(ctx.client, timeout=120)
    except SetupCancel:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedCancel, components=None)
        else:
            await ctx.edit_response(snowflake, embedCancel, components=None)
        raise SetupCancel
    except asyncio.TimeoutError:
        if isinstance(ctx, ComponentInteraction):
            await ctx.edit_initial_response(embed=embedTimeout, components=None)
        else:
            await ctx.edit_response(snowflake, embedTimeout, components=None)
        raise asyncio.TimeoutError
    except:
        logger.error(sys.exc_info())
        return
    
    return selectObj.selected_guilds
