import sys
from asgiref.sync import sync_to_async
import asyncio

import arrow

from django.conf import settings

from hikari import ButtonStyle, ComponentInteraction, Embed, Emoji, InteractionCreateEvent, Message, PartialGuild, MessageFlag
from hikari.impl import ContainerComponentBuilder, TextDisplayComponentBuilder, MessageActionRowBuilder, LinkButtonBuilder
from hikari.interactions.base_interactions import ResponseType
import lightbulb

from cache.helpers import save_discord_meta_models

from app.models import Events, Config, Option_Presets, Templates

from discord.hashids import Hashids

from bot.bot.utils.exceptions import SetupCancel
from bot.bot.modules.events.classes.calendar import Calendar
from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.Getters import AwaitInteraction
from bot.bot.utils.placeholders import timeoutEmbed
from bot.bot.utils.util import CanManage_
from bot.bot.utils.discord_utils import GetBool
from bot.bot.utils.event_utils import RunEventBuilder, UpdateEvent, CopyEvent, update_event_thread, update_other_events_messages

from loguru import logger

from django.conf import settings
SALT = getattr(settings, 'HASH_SALT', None)
IS_LOCAL = getattr(settings, 'LOCAL')

loader = lightbulb.Loader()

premium_components = [
    ContainerComponentBuilder(
        components=[
            TextDisplayComponentBuilder(content="This guild has reached the maximum number of recurring events.\nTo post more recurring events, please upgrade to premium."),
            MessageActionRowBuilder(
                components=[
                    LinkButtonBuilder(
                        url="https://baast.app/pricing",
                        label="Premium",
                    ),
                ]
            ),
        ]
    ),
]


def GetUser(users, index):
    return users[index]

@loader.listener(InteractionCreateEvent)
async def manager_interaction(evt: InteractionCreateEvent, client: lightbulb.Client) -> None:
    if type(evt.interaction) is not ComponentInteraction:
        return
    
    interaction: ComponentInteraction = evt.interaction
    
    if interaction.custom_id not in ['bastEvSetting']:# manageButtonNames:
        return
    
    await interaction.create_initial_response(response_type=ResponseType.DEFERRED_MESSAGE_CREATE, content="....", flags=MessageFlag.EPHEMERAL | MessageFlag.IS_COMPONENTS_V2)
    await save_discord_meta_models(interaction)

    if interaction.user == None:
        logger.warning(f'Interaction Event contains a `None` User for message {interaction.message.id}')
        return
    
    guild: PartialGuild = await interaction.app.rest.fetch_guild(interaction.get_guild())
    
    if not await CanManage_(interaction, guild):
        await interaction.edit_initial_response(content="You do not have permissions required to-do this.")
        return
    
    message = interaction.message
    
    config: Config = await sync_to_async(Config.objects.get)(guild = int(guild.id))

    try:
        event: Events = await sync_to_async(Events.objects.get)(gid=config, message=int(message.id))
    except Events.DoesNotExist:
        return
    
    hashids = Hashids(salt=SALT)
    
    buttons = (interaction.app.rest.build_message_action_row()
                    .add_interactive_button(ButtonStyle.SECONDARY, 'bastEvEdit', emoji=Emoji.parse('<:edit:1080846207196348416>'))
                    .add_interactive_button(ButtonStyle.SECONDARY, 'bastEvCopy', emoji=Emoji.parse('<:copy:1127727865912377394>'))
                    .add_interactive_button(ButtonStyle.SECONDARY, 'bastEvDelete', emoji=Emoji.parse('<:trash:1080985968452055130>'))
                    .add_link_button(f"https://{'localhost' if IS_LOCAL else 'baast.app'}/panel/{hashids.encode(int(guild.id))}/event/{event.id}/", label="Panel"))
    
    if config.is_premium and event.worksheet_id != None and config.p_sheetid != None:
        buttons.add_link_button(f"https://docs.google.com/spreadsheets/d/{config.p_sheetid}/edit#gid={event.worksheet_id}", label="Spread Sheet")
    
    rsp: Message = await interaction.edit_initial_response(component=buttons)
    
    try:
        val, i = await AwaitInteraction(interaction, interaction.user, ['bastEvEdit', 'bastEvCopy', 'bastEvDelete'], auto_respond=False, timeout=120)
    except asyncio.TimeoutError:
        await interaction.edit_initial_response(content=timeoutEmbed, component=None)
        return
    except:
        logger.error(sys.exc_info())
        return
    else:
        val = val[0]
        
    if val == 'bastEvEdit':
        try:
            option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
            template: Templates = await sync_to_async(event.GetTemplate)()
        except:
            logger.error(sys.exc_info())
            return
        #
        # START Builder
        # 
        try:
            data, date, recuringInterval, recuringUntil, keep_signup_data, mentions = await RunEventBuilder(
                interaction, client, rsp, template, option_preset, interaction.member.user, event=event,
                reccuring_events_count=await sync_to_async(Events.objects.filter(gid=config, recurring_interval__gt=0).count)() if not config.is_premium else 0)
        except SetupCancel:
            return
        except asyncio.TimeoutError:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        #
        # UPDATE Event
        #
        embeds, componentRow, event, logs, thread_logs = await UpdateEvent(interaction, client, config, event, option_preset, data, date, 
                                                             recuringInterval, recuringUntil, keep_signup_data, interaction.user)

        await message.edit(embeds=embeds, components=componentRow)
        
        ## Edit a Google Calendar Event
        if config.calendar_enabled and event.calendar_event_id != None and config.is_premium:
            try:
                cal: Calendar = Calendar()
            except:
                logger.error(sys.exc_info())
            else:   
                if config.calendar_id != None and cal.check_calendar_exists(config.calendar_id):   
                    try:
                        await sync_to_async(cal.edit_event)(event, config)
                    except:
                        logger.error(sys.exc_info())
        
                
        await update_event_thread(interaction.app.rest, event)
        
        await update_other_events_messages(interaction.app.rest, event, guild)
        
        await interaction.edit_initial_response(content=Embed(description=f"Finished Editing Event [{event.title}]({message.make_link(guild)}) <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"), component=None)
        
        
        #LOG
        if config.log_channel:
            logs.insert(0, Embed(description=f"{interaction.user.mention} edit event [{event.title}]({message.make_link(guild)}) <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"))
            
            if logs.__len__() > 0:
                await (await config.log(guild)).send(embeds=logs)
        
        if event.thread != None and thread_logs.__len__() > 0:
            event_thread = await interaction.app.rest.fetch_channel(event.thread)
            await event_thread.send(embeds=thread_logs)
            
    if val == 'bastEvCopy':
        if config.is_premium:
            try:
                event, eventMsg = await CopyEvent(interaction, client, guild, config, event)
            except asyncio.TimeoutError:
                await interaction.edit_initial_response(content=timeoutEmbed, component=None)
                return
            
            await interaction.edit_initial_response(content=Embed(description=f"Finished Copying Event as [{event.title}]({eventMsg.make_link(guild)}) <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"), component=None)
        else:
            await interaction.edit_initial_response(components=premium_components)
        
    elif val == 'bastEvDelete':
        try:
            result = await GetBool(interaction, client, message.id, 
                               description=f'Are you sure you want to delete the event **[{event.title}]({message.make_link(guild)})**', 
                               yes='Yes', no='No')
        except asyncio.TimeoutError:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        
        if result:
            #await event.async_delete() #not a good idea to delete the event since clean-up is handled by message delete listener
            
            msg = await interaction.fetch_message(event.message)
            await msg.delete()
            
            await interaction.edit_initial_response(content=Embed(description=f"Finished Deleting Event **{event.title}** <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"), component=None)
    
            #LOG
            if config.log_channel:
                await (await config.log(guild)).send(embed=Embed(description=f"{interaction.user.mention} deleted event **{event.title}**  <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"))
            
        elif not result:
            await interaction.edit_initial_response(content=None, component=None)
    

    # elif interaction.custom_id in 'bastEvUsers':
    #     try:
    #         attendance = Attendance.objects.get(id=evnt.id)
    #     except Attendance.DoesNotExist:
    #         return await interaction.create_initial_response(response_type=ResponseType.DEFERRED_MESSAGE_UPDATE)
    #     await interaction.create_initial_response(response_type=ResponseType.MESSAGE_CREATE, content=f"**Current Attending:**\n`{await attendance.attending()}`\n`{await attendance.tentative()}`\n`{await attendance.declined()}`", flags=MessageFlag.EPHEMERAL)
