import sys
from asgiref.sync import sync_to_async

from django.db.models import QuerySet

from hikari import ComponentInteraction, Embed, GuildTextChannel, InteractionCreateEvent
import lightbulb

from app.models import Events, Events_Links, Config, Option_Presets, Attendance, Attendance_Linked

from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.event_utils import RebuildEventEmbed, isUserAnyAttendingSignupOption, update_other_events_messages
from bot.bot.utils.enums import SignupOption


from loguru import logger


loader = lightbulb.Loader()
buttonNames = ['baastConfirm', 'baastDecline']

def GetUser(users, index):
    return users[index]

@loader.listener(InteractionCreateEvent)
async def checkin_interaction(evt: InteractionCreateEvent) -> None:
    if type(evt.interaction) is not ComponentInteraction:
        return

    interaction: ComponentInteraction = evt.interaction
    
    if interaction.user == None:
        logger.warning(f'An Interaction Event contained a null User for message {interaction.message.id}')
        return
    
    if interaction.custom_id not in buttonNames:
        return
    
    guild = interaction.get_guild()
    config: Config = await sync_to_async(Config.objects.get)(guild = int(guild.id))
    
    if not config.is_premium:
        return
    
    thread: GuildTextChannel = await evt.interaction.app.rest.fetch_channel(interaction.channel_id)
    
    event: Events = None
    isLinkedEvent: bool = False
    linkedEvent: Events_Links = None
    
    try:
        event: Events = await sync_to_async(Events.objects.get)(gid=config, thread=int(thread.id))
    except Events.DoesNotExist:
        ## LINKED EVENT
        try:
            linkedEvent: Events_Links = await sync_to_async(Events_Links.objects.get)(linked_guild=config, thread=int(thread.id))
        except Events_Links.DoesNotExist:
            return
        except:
            logger.critical(sys.exc_info())
            return
        else:
            isLinkedEvent = True
            event: Events = await sync_to_async(linkedEvent.Event)()
    except:
        logger.critical(sys.exc_info())
        return
    
    les: QuerySet = await sync_to_async(Events_Links.objects.filter)(event_id=event)
    if isLinkedEvent:
        les = await sync_to_async(les.exclude)(linked_guild=config)
    linkedEvents: list[Events_Links] = await sync_to_async(list)(les)
    
    linkedAttendances: list[Attendance_Linked] = []
    for le in linkedEvents:
        linkedAttendances.append(await sync_to_async(le.GetAttendance)())
    
    mainAttendance: Attendance = await sync_to_async(event.GetAttendance)()
    linkedAttendance: Attendance_Linked = None
    if isLinkedEvent:
        linkedAttendance = await sync_to_async(linkedEvent.GetAttendance)()
        
      
    if (
        ((linkedAttendance) if isLinkedEvent else (mainAttendance)).isConfirmed(int(interaction.user.id)) and 
        interaction.custom_id == 'baastDecline' and 
        await isUserAnyAttendingSignupOption(int(interaction.user.id), ((linkedAttendance) if isLinkedEvent else (mainAttendance)), event)
        ):
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).remove_confirmed)(int(interaction.user.id))
        
        await thread.send(embed=Embed(description=f'{interaction.user.mention} has declined the check-in.', colour=0xed4245))
        
        option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        lastOption = ((linkedAttendance) if isLinkedEvent else (mainAttendance)).get_signup_option(int(interaction.user.id))
        
        # Remove their Role Signup 
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).remove_signup_option)(lastOption, int(interaction.user.id))
        # If default preset then set them as declined
        if option_preset.name == "Default" and option_preset.id == 1:
            await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).set_signup_option)(SignupOption.Option_2, int(interaction.user.id))
        
        await interaction.app.rest.remove_thread_member(((linkedEvent.thread) if isLinkedEvent else (event.thread)), interaction.user)
        
    elif (interaction.custom_id == 'baastConfirm' 
          and not ((linkedAttendance) if isLinkedEvent else (mainAttendance)).isConfirmed(int(interaction.user.id)) 
          and await isUserAnyAttendingSignupOption(int(interaction.user.id), ((linkedAttendance) if isLinkedEvent else (mainAttendance)), event)):
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).set_confirmed)(int(interaction.user.id))
        
        await thread.send(embed=Embed(description=f'{interaction.user.mention} has reaffirmed they will be attending this event.', colour=0x3ba55c))
    else:
        return
 
    message = await interaction.app.rest.fetch_message(int(event.channel), int(event.message))
    
    # Rebuild Event Embed
    try:
        eventEmbeds = await RebuildEventEmbed(interaction.app.rest, event, (linkedAttendance if isLinkedEvent else mainAttendance), linkedAttendances, mainAttendance)
    except:
        logger.warning(sys.exc_info())
    else:
        await message.edit(embeds=eventEmbeds)
    
    try:
        await update_other_events_messages(interaction.app, event, guild)
    except:
        logger.warning(sys.exc_info())
    ##
    
    ##ID do wonder if this should be a task to mitigate the risk of rate limiting/ cost #908
    if config.is_premium and event.worksheet_id != None:
        try:
            sheets = Sheet(config, guild.name, event)
        except:
            logger.error(sys.exc_info())
        else:
            await sheets.UpdateAttendance(event)