import asyncio
import sys

from loguru import logger

from asgiref.sync import sync_to_async

import lightbulb
import hikari
from hikari import Embed, InteractionType, PartialGuild, ResponseType, GuildChannel, ComponentType, Message, Permissions

from app.models import Config

from bot.bot.utils.exceptions import DisabledDMs, NoValues
from bot.bot.utils.util import HasChannelPermission
from cache.helpers import _safe_get_cache_view



async def AwaitInteraction(ctx: lightbulb.Context, user: hikari.User, interationIDs: list[str], auto_respond: bool = True, timeout: int = 120) -> tuple[list[str], hikari.ComponentInteraction]:
    try:
        event = await ctx.app.wait_for(hikari.InteractionCreateEvent, predicate=lambda e: isinstance(e.interaction, hikari.ComponentInteraction) and e.interaction.user.id == user.id and e.interaction.custom_id in interationIDs, timeout=timeout)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError

    inter: hikari.ComponentInteraction = event.interaction
    if auto_respond:
        await inter.create_initial_response(response_type=6)

    # Maybe disable the button/select?
    if(inter.component_type == ComponentType.BUTTON):
        return [inter.custom_id], inter
    else:
        return inter.values, inter

async def AwaitInteractionNoUser(ctx: lightbulb.Context, linkedGuild: PartialGuild, interationIDs: list[str]) -> tuple[list[str], hikari.ComponentInteraction]:
    try:
        event = await ctx.app.wait_for(hikari.InteractionCreateEvent, predicate=lambda e: isinstance(e.interaction, hikari.ComponentInteraction) and e.interaction.custom_id in interationIDs and e.interaction.guild_id == linkedGuild.id, timeout=120)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError

    inter: hikari.ComponentInteraction = event.interaction
    await inter.create_initial_response(response_type=6)

    # Maybe disable the button/select?
    if(inter.component_type == ComponentType.BUTTON):
        return [inter.custom_id], inter
    else:
        return inter.values, inter

async def AwaitModalInteraction(ctx: lightbulb.Context, user: hikari.User, modalID: str, timeout: int = 120) -> list[str]:
    try:
        event = await ctx.app.wait_for(hikari.InteractionCreateEvent, predicate=lambda e: isinstance(e.interaction, hikari.ModalInteraction) and e.interaction.user.id == user.id and e.interaction.custom_id == modalID, timeout=timeout)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError

    # print(event.interaction)
    # print('---------------------------')
    # print(event.interaction.custom_id)

    inter: hikari.ModalInteraction = event.interaction
    await inter.create_initial_response(response_type=ResponseType.DEFERRED_MESSAGE_UPDATE)

    # Maybe disable the button/select?
    if(inter.type == InteractionType.MODAL_SUBMIT):
        values: list[str] = []
        for actionRow in inter.components:
            for c in actionRow.components:
                if c.type == ComponentType.TEXT_INPUT:
                    values.append(c.value)

        return values#, inter
    else:
        return None#, inter


async def GetChannels(ctx: lightbulb.Context | hikari.ComponentInteraction, 
                        user: hikari.User, 
                        guild: hikari.Guild, 
                        title: str, 
                        response: Message = None, 
                        description: str = None, 
                        min: int = 1, 
                        max: int = 20,
                        color: hikari.Color = hikari.Color(0x006F79),
                        favs: list[hikari.TextableChannel] = [], 
                        reqPerms: hikari.Permissions = hikari.Permissions.SEND_MESSAGES | hikari.Permissions.VIEW_CHANNEL
                    ) -> list[hikari.TextableChannel]:
    channelSelects = await GetChannelsActionRow(ctx, reqPerms=reqPerms)

    embed = Embed(
        title = title,
        description = description,
        color = color
    )

    amount = max
    selectedChnls = []
    for i, s in enumerate(channelSelects, 1):
        try:
            embed.set_footer(f'Part {i}/{len(channelSelects)}')
            if not response:
                await user.send(embed=embed, component=s.parent)
            else:
                await response.edit(embed=embed, component=s.parent)
        except:
            logger.critical(f'{sys.exc_info()}')

        chnlsIDs, _i = await AwaitInteraction(ctx, user, ['get_Channels'])

        for id in chnlsIDs:
            if id != 'none':
                selectedChnls.append(guild.get_channel(id))
                amount -= 1

                if amount == 0:
                    return selectedChnls

    return selectedChnls

async def GetChannelsFromInteraction(interaction: hikari.ComponentInteraction, 
                                        user: hikari.User, 
                                        guild: hikari.Guild, 
                                        title: str, 
                                        description: str = None, 
                                        min: int = 1, 
                                        max: int = 20,
                                        color: hikari.Color = hikari.Color(0x006F79),
                                        favs: list[hikari.TextableChannel] = [], 
                                        reqPerms: Permissions = Permissions.SEND_MESSAGES | Permissions.VIEW_CHANNEL
                                    ) -> list[hikari.TextableChannel]:

    channelSelects = await GetChannelsActionRow(interaction, reqPerms=reqPerms)

    embed = Embed(
        title = title,
        description = description,
        color = color
    )

    amount = max
    
    selectedChnls = []
    for i, s in enumerate(channelSelects, 1):
        try:
            embed.set_footer(f'Part {i}/{len(channelSelects)}')
            await interaction.edit_initial_response(embed=embed, component=s.parent)
        except:
            logger.critical(f'{sys.exc_info()}')

        chnlsIDs, _i = await AwaitInteraction(interaction, user, ['get_Channels'])

        for id in chnlsIDs:
            if id != 'none':
                selectedChnls.append(guild.get_channel(id))
                amount -= 1

                if amount == 0:
                    return selectedChnls

    return selectedChnls


async def GetV2RolesFromGuild(ctx: lightbulb.Context, user: hikari.User, title: str, description: str = None, min: int = 1, max: int = 20, color: hikari.Color = hikari.Color(0x006F79), footerText: str = None, enableEveryone: bool = False) -> list[hikari.Role]:
    embed = Embed(
        title = title,
        description = description,
        #timestamp = datetime.utcnow().astimezone(),
        color = color
    )
    embed.set_footer(text = footerText)

    selectMenu = (
        ctx.app.rest.build_message_action_row()
        .add_select_menu(ComponentType.ROLE_SELECT_MENU, 'get_Roles', placeholder="Select Role(s)", min_values=min, max_values=max)
    )

    try:
        await user.send(component=selectMenu)
    except hikari.UnauthorizedError:
        raise DisabledDMs

    roleIDs = await AwaitInteraction(ctx, user, ['get_Roles'])


async def GetRoles(ctx: lightbulb.Context | hikari.ComponentInteraction, 
                   user: hikari.User, 
                   guild: hikari.Guild, 
                   title: str, 
                   response: Message = None, 
                   description: str = None, 
                   min: int = 1, max: int = 20, 
                   color: hikari.Color = hikari.Color(0x006F79),
                   enableEveryone: bool = False
                ) -> list[hikari.Role]:
    
    roles = _safe_get_cache_view(guild.get_roles, f"guild {guild.id} roles")

    if len(roles) < 1:
        raise NoValues

    embed = Embed(
        title = title,
        description = description,
        #timestamp = datetime.utcnow().astimezone(),
        color = color
    )

    selectedRoles = []
    splitRoles = [roles[i:i + 20] for i in range(0, len(roles), 20)]

    amount = max
    for i, s in enumerate(splitRoles, 1):
        selectMenu = ctx.app.rest.build_message_action_row().add_text_menu('get_Roles', placeholder="Select Role(s)", min_values=min, max_values=amount)

        selectMenu.add_option('None', 'none')
        for r in s:
            selectMenu.add_option(r.name, str(r.id))

        try:
            embed.set_footer(f'Part {i}/{len(splitRoles)}')
            if not response:
                await user.send(embed=embed, component=selectMenu.parent)
            else:
                await response.edit(embed=embed, component=selectMenu.parent)
        except hikari.UnauthorizedError:
            raise DisabledDMs
        except:
            logger.error(sys.exc_info())

        roleIDs, _i = await AwaitInteraction(ctx, user, ['get_Roles'])

        for id in roleIDs:
            if id != 'none':
                selectedRoles.append(guild.get_role(id))
                amount -= 1
                if amount == 0:
                    return selectedRoles

    return selectedRoles



async def GetChannelsActionRow(ctx: lightbulb.Context, reqPerms: hikari.Permissions = hikari.Permissions.SEND_MESSAGES | hikari.Permissions.VIEW_CHANNEL, reqNone: bool = True, min: int = 1, max: int = 20) -> list[hikari.api.TextSelectMenuBuilder]:
    config: Config = await sync_to_async(Config.objects.get)(guild=ctx.get_guild().id)
    guild = await ctx.client.rest.fetch_guild(ctx.guild_id)
    
    cachedChannels = await ctx.client.rest.fetch_guild_channels(guild)
    #cachedChannels = guild.get_channels()
    
    textChnls = []
    for val in cachedChannels:
        val: GuildChannel = val
        if val.type.value == 0:
            if HasChannelPermission(val, guild, guild.get_my_member(), reqPerms):
                textChnls.append({"valid":True, "channel":val})
            elif HasChannelPermission(val, guild, guild.get_my_member(), hikari.Permissions.SEND_MESSAGES | hikari.Permissions.VIEW_CHANNEL):#MANAGE_THREADS
                for perm in reqPerms:
                    if not HasChannelPermission(val, guild, guild.get_my_member(), perm):
                        textChnls.append({"valid":False, "channel":val, "perm":perm})
                        break
    
    if len(textChnls) < 1:
        raise NoValues

    split_templates = [
        textChnls[i:i + 19] for i in range(0, len(textChnls), 19)
    ]  # Split the list into chunks of size 20
    
    selectMenus = []
    for i, s in enumerate(split_templates, 1):
        selectMenu = ctx.client.rest.build_message_action_row().add_text_menu('get_Channel', placeholder="Select a Channnel", min_values=min, max_values=max)
        if reqNone:
            selectMenu.add_option('None', '0', 
                                  description=None, 
                                  emoji=hikari.Emoji.parse('<:validchannel:1120728238667346051>'))
        
        for t in s:
            selectMenu.add_option(f'{t["channel"].name}', str(t["channel"].id), 
                                  description=None if t["valid"] else f'Missing Permission:\n {str(t["perm"].name)}', 
                                  emoji=hikari.Emoji.parse('<:validchannel:1120728238667346051>' if t["valid"] else '<:invalidchannel:1120728255633301526>'))
        
            
        selectMenus.append(selectMenu)
    return selectMenus

async def GetTextChannelsActionRow(ctx: lightbulb.Context, includeEveryone: bool = True) -> list[hikari.ActionRowComponent]:
    config: Config = await sync_to_async(Config.objects.get)(guild=ctx.get_guild().id)
    guild = ctx.get_guild()
    
    cachedChannels = _safe_get_cache_view(guild.get_channels, f"guild {guild.id} channels")
    
    textChnls = []
    for channel in cachedChannels:
        if channel.type == hikari.ChannelType.GUILD_TEXT:
            textChnls.append(channel)
                

    if len(textChnls) < 1:
        raise NoValues

    split_templates = [
        textChnls[i:i + 20] for i in range(0, len(textChnls), 20)
    ]  # Split the list into chunks of size 20
    
    selectMenus = []
    for i, s in enumerate(split_templates, 1):
        selectMenu = ctx.app.rest.build_message_action_row().add_text_menu('get_Channel', placeholder="Select a Channnel", min_values=1, max_values=1)
        #selectMenu = ctx.app.rest.build_message_action_row().add_channel_menu('get_Channel', placeholder="Select a Channnel", min_values=1, max_values=1, channel_types=[ChannelType.GUILD_TEXT])

        for t in s:
            selectMenu.add_option(f'{t["channel"].name}', str(t["channel"].id), 
                                  description=None if t["valid"] else f'Missing Permission:\n {str(t["perm"].name)}', 
                                  emoji=hikari.Emoji.parse('<:validchannel:1120728238667346051>' if t["valid"] else '<:invalidchannel:1120728255633301526>'))
        
            
        selectMenus.append(selectMenu)
    return selectMenus