import sys
from arrow import Arrow
from datetime import datetime, timedelta, UTC
from asgiref.sync import sync_to_async

from django.db.models import QuerySet
from django.conf import settings

from django.db.utils import DataError
from hikari import ComponentInteraction, Embed, InteractionCreateEvent, GatewayGuild, errors, User, MessageFlag
from hikari.api.rest import RESTClient
from hikari.interactions.base_interactions import ResponseType
import lightbulb

from cache.helpers import save_discord_meta_models

from app.models import Events, Events_Links, Config, Option_Presets, Attendance, Attendance_Linked, Preset_Roles, Stats_Responded

from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.thread_helpers import ThreadHasUser
from bot.bot.utils.util import ConvertTimeFromDBToValues, CanManage_
from bot.bot.utils.event_utils import (BuildComponents, RebuildEventEmbed, update_other_events_messages, buttonNames)
from bot.bot.utils.enums import SignupOption

from loguru import logger

from django.conf import settings
SALT = getattr(settings, 'HASH_SALT', None)

loader = lightbulb.Loader()


def GetUser(users, index):
    return users[index]

@loader.listener(InteractionCreateEvent)
async def signup_interaction(evt: InteractionCreateEvent) -> None:
    if type(evt.interaction) is not ComponentInteraction:
        return
    if evt.interaction.custom_id not in buttonNames:
        return
    
    interaction: ComponentInteraction = evt.interaction
    await interaction.create_initial_response(response_type=ResponseType.DEFERRED_MESSAGE_CREATE, flags=MessageFlag.EPHEMERAL | MessageFlag.SUPPRESS_EMBEDS)
    
    await save_discord_meta_models(interaction)

    if interaction.user == None:
        logger.warning(f'Interaction Event contains a `None` User for message {interaction.message.id}')
        return
    
    guild: GatewayGuild = interaction.get_guild()
    message = interaction.message
    
    config: Config = await sync_to_async(Config.objects.get)(guild = int(guild.id))
    
    event: Events = None
    isLinkedEvent: bool = False
    linkedEvent: Events_Links = None
    now = datetime.now(UTC)
    
    try:
        event: Events = await sync_to_async(Events.objects.get)(gid=config, message=int(message.id))
    except Events.DoesNotExist:
        ## LINKED EVENT
        try:
            linkedEvent: Events_Links = await sync_to_async(Events_Links.objects.get)(linked_guild=config, message=int(message.id))
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
    
    option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
    roleset: Preset_Roles = await sync_to_async(event.GetRoleset)()
    
    mainAttendance: Attendance = await sync_to_async(event.GetAttendance)()
    linkedAttendance: Attendance_Linked = None
    if isLinkedEvent:
        linkedAttendance = await sync_to_async(linkedEvent.GetAttendance)()
    
    
    lastOption = ((linkedAttendance) if isLinkedEvent else (mainAttendance)).get_signup_option(int(interaction.user.id))
    newOption = SignupOption(buttonNames.index(interaction.custom_id))
    
    
    # CASE SWITCH
    if lastOption != None and lastOption != newOption: 
        
        #Remove Users Last Selected Option
        if roleset != None and roleset.roles[lastOption.value]["role_id"] != None and roleset.roles[lastOption.value]["role_id"].lower() != 'none':
            try:
                await remove_role(evt.app.rest, guild, interaction.user, roleset.roles[lastOption.value]["role_id"])
            except:
                logger.error(sys.exc_info())
                
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).remove_signup_option)(lastOption, int(interaction.user.id))
        
        #Set Users New Selected Option
        if roleset != None and roleset.roles[newOption.value]["role_id"] != None and roleset.roles[newOption.value]["role_id"].lower() != 'none':
            try:
                await add_role(evt.app.rest, guild, interaction.user, roleset.roles[newOption.value]["role_id"])
            except:
                logger.error(sys.exc_info())
                
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).set_signup_option)(SignupOption(buttonNames.index(interaction.custom_id)), int(interaction.user.id))
        
    elif lastOption == newOption:
        if option_preset.name != "Default" and option_preset.id != 1: # If not default preset remove their signup
            if roleset != None and roleset.roles[lastOption.value]["role_id"] != None and roleset.roles[lastOption.value]["role_id"].lower() != 'none':
                try:
                    await remove_role(evt.app.rest, guild, interaction.user, roleset.roles[lastOption.value]["role_id"])
                except:
                    logger.error(sys.exc_info())
                    
            await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).remove_signup_option)(SignupOption(buttonNames.index(interaction.custom_id)), int(interaction.user.id))
            
        if ((linkedAttendance) if isLinkedEvent else (mainAttendance)).isConfirmed(int(interaction.user.id)):
            await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).remove_confirmed)(int(interaction.user.id))
            
            await evt.app.rest.create_message(((linkedEvent.thread) if isLinkedEvent else (event.thread)), embed=Embed(description=f'{interaction.user.mention} has removed their sign-up and thus no longer confirmed for this event.', colour=0xed4245))
        
    elif lastOption == None and newOption != None:
        #Set Users New Selected Option
        if roleset != None and roleset.roles[newOption.value]["role_id"] != None and roleset.roles[newOption.value]["role_id"].lower() != 'none':
            try:
                await add_role(evt.app.rest, guild, interaction.user, roleset.roles[newOption.value]["role_id"])
            except:
                logger.error(sys.exc_info())
                
        await sync_to_async(((linkedAttendance) if isLinkedEvent else (mainAttendance)).set_signup_option)(SignupOption(buttonNames.index(interaction.custom_id)), int(interaction.user.id))
        
        
        # Stats
        stat:QuerySet[Stats_Responded] = await sync_to_async(Stats_Responded.objects.filter)(gid=config.id, event_id=event.id, user_id=int(interaction.user.id))
        stat = await sync_to_async(list)(stat)
        if not stat or (stat and event.recurring_until != 0 and stat[len(stat)-1].date < event.event_date):
            duration = now - event.created_date if event.recurring_interval == 0 or (event.event_date - timedelta(days=event.recurring_interval)) < event.created_date else now - (event.event_date - timedelta(days=event.recurring_interval))
            hours: int = (int)(divmod(duration.total_seconds(), 3600)[0])
            
            try:
                await sync_to_async(Stats_Responded.objects.create)(gid=config.id, event_id=event.id, user_id=int(interaction.user.id), hours_after=hours)
            except DataError as e:
                logger.warning(f'DataError creating stats response for user {interaction.user.id} for event {event.id}: {e}')
            except Exception as e:
                logger.error(f'Error creating stats response: {e}')
        
    else:
        logger.warning(f'Something went wrong with interaction {interaction.custom_id} for event {event.id}')
    # END CASE SWITCH
    
    
    if lastOption != newOption and newOption != None:
        await interaction.edit_initial_response(content=f"Thank you for signing up as {option_preset.options[buttonNames.index(interaction.custom_id)]['label']} for [{event.title}]({interaction.message.make_link(guild)})!")
    
    
    # Rebuild Event Embed
    try:
        eventEmbeds = await RebuildEventEmbed(interaction.app.rest, event, (linkedAttendance if isLinkedEvent else mainAttendance), linkedAttendances, mainAttendance)
    except:
        logger.warning(sys.exc_info())
    else:
        await message.edit(embeds=eventEmbeds, 
                           components=await BuildComponents(interaction.app.rest, config, option_preset, event.date_arrow, linked=True if isLinkedEvent else False, linkedID=linkedEvent.id if isLinkedEvent else None))
    
    try:
        await update_other_events_messages(interaction.app.rest, event, guild)
    except:
        logger.warning(sys.exc_info())
    ##
    
    try:
        threadMembers = await evt.app.rest.fetch_thread_members(((linkedEvent.thread) if isLinkedEvent else (event.thread)))
    except errors.NotFoundError:
        pass
    except:
        logger.warning(sys.exc_info())
    else:
        isThreadMember = await ThreadHasUser(threadMembers, interaction.user)

        try:
            if (lastOption == newOption or (isThreadMember and 
                (option_preset.options[buttonNames.index(interaction.custom_id)]['istentative'] or 
                option_preset.options[buttonNames.index(interaction.custom_id)]['send_notifcations'] == False))):
                await evt.app.rest.remove_thread_member(((linkedEvent.thread) if isLinkedEvent else (event.thread)), interaction.user)
            elif (not isThreadMember and 
                    option_preset.options[buttonNames.index(interaction.custom_id)]['send_notifcations'] and
                    not option_preset.options[buttonNames.index(interaction.custom_id)]['istentative']):
                await evt.app.rest.add_thread_member(((linkedEvent.thread) if isLinkedEvent else (event.thread)), interaction.user)
        except errors.ForbiddenError:
            logger.warning(sys.exc_info())
            pass
        except Exception as e:
            logger.error(f'Error removing/adding thread member: {e}')
    
    ##ID do wonder if this should be a task to mitigate the risk of rate limiting/ cost #908
    if config.is_premium and event.worksheet_id != None:
        try:
            sheets = Sheet(config, guild.name, event)
        except:
            logger.error(sys.exc_info())
        else:
            await sheets.UpdateAttendance(event)
        

    #
    # LOG
    #
    try:
        if config.log_channel:
            reminderTimeDate = config.signupDate(event.date_arrow)
            if Arrow.utcnow() < reminderTimeDate:
                if lastOption == None:
                    await (await config.log(guild)).send(embed=Embed(description=f"{interaction.user.mention} signed up as **{option_preset.options[buttonNames.index(interaction.custom_id)]['label']}** for event "
                                                                    f"**[{event.title}]({message.make_link(guild)})** <t:{int(event.event_date.timestamp())}:R>"))
                elif lastOption != None and lastOption != newOption:
                    await(await config.log(guild)).send(embed=Embed(description=f"{interaction.user.mention} switched from **{option_preset.options[lastOption.value]['label']}** "
                                                    f"to **{option_preset.options[buttonNames.index(interaction.custom_id)]['label']}** for event **[{event.title}]({message.make_link(guild)})**"
                                                    f" <t:{int(event.event_date.timestamp())}:R>"))
                elif lastOption == newOption:
                    await (await config.log(guild)).send(embed=Embed(description=f"{interaction.user.mention} removed their sign-up as **{option_preset.options[buttonNames.index(interaction.custom_id)]['label']}** for event "
                                                                    f"**[{event.title}]({message.make_link(guild)})** <t:{int(event.event_date.timestamp())}:R>"))

    except:
        logger.warning(sys.exc_info())

async def remove_role(rest: RESTClient, guild: GatewayGuild, user: User, role_id: int):
    try:
        await rest.remove_role_from_member(guild, int(user.id), role_id)
    except errors.ForbiddenError:
        logger.warning(f'Bot does not have permission to remove role {role_id} from {user.mention} in guild {guild.id}')
    except errors.NotFoundError:
        logger.warning(f'Role {role_id} not found for {user.mention} in guild {guild.id}')
    except Exception as e:
        logger.error(f'Error removing role {role_id} from {user.mention} in guild {guild.id}: {e}')

async def add_role(rest: RESTClient, guild: GatewayGuild, user: User, role_id: int):
    try:
        await rest.add_role_to_member(guild, int(user.id), role_id)
    except errors.ForbiddenError:
        logger.warning(f'Bot does not have permission to add role {role_id} to {user.mention} in guild {guild.id}')
    except errors.NotFoundError:
        logger.warning(f'Role {role_id} not found for {user.mention} in guild {guild.id}')
    except Exception as e:
        logger.error(f'Error adding role {role_id} to {user.mention} in guild {guild.id}: {e}')