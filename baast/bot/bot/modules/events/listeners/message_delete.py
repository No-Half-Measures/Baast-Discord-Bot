import sys
import arrow

from asgiref.sync import sync_to_async

from hikari import Embed, Color, GatewayGuild, NotFoundError, Permissions, GuildTextChannel, GuildMessageDeleteEvent, RESTAware, ForbiddenError
import lightbulb

from loguru import logger

from cache.helpers import save_discord_meta_models

from django.db.models import QuerySet
from discord.models import User

from app.models import Events, Config, Events_Links, Option_Presets, Attendance, Preset_Roles

from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.modules.events.classes.calendar import Calendar
from bot.bot.utils.enums import SignupOption
from bot.bot.utils.util import HasChannelPermission



loader = lightbulb.Loader()


def GetUser(users, index):
    return users[index]

@loader.listener(GuildMessageDeleteEvent)
async def message_delete(evt: GuildMessageDeleteEvent) -> None:
    if type(evt) is not GuildMessageDeleteEvent:
        return

    await save_discord_meta_models(evt)
    
    guild = evt.get_guild()
    if guild == None:
        return
    
    try:
        config: Config = await sync_to_async(Config.objects.get)(guild = int(guild.id))
    except Config.DoesNotExist:
        return
    except:
        logger.error(sys.exc_info())
        return

    try:
        event: Events = await sync_to_async(Events.objects.get)(gid=config, message=int(evt.message_id))
    except Events.DoesNotExist:
        pass
    except:
        logger.error(sys.exc_info())
        return
    else:
        await DeleteEvent(evt, event, config)
        return
    
    try:
        event: Events_Links = await sync_to_async(Events_Links.objects.get)(linked_guild=config, message=int(evt.message_id))
    except Events_Links.DoesNotExist:
        return
    except:
        logger.error(sys.exc_info())
        return
    else:
        await DeleteLinkedEvent(evt, event, config)
        return
    
async def DeleteEvent(evt: GuildMessageDeleteEvent, event: Events, config: Config):
    if event.thread == None:
        logger.error(f'No thread for event {event.id}') ## CHANGE, maybe just recreat the thread and then continue but also log it in the guilds log chnanel??
        return
    
    guild = evt.get_guild()
    now = arrow.utcnow()
    logEmbeds = []
    archive: bool = arrow.get(event.event_date).to('utc') <= now
    
    if archive:
        attendanceEmbd = Embed(
            title = event.title,
            description = event.description,
            color = Color(0x228b22)
        )
        
        attendanceEmbd.add_field(name='Date', 
            value= f"<t:{int(event.event_date.timestamp())}:F>", 
            inline=False )
        
        option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        roleset: Preset_Roles = await sync_to_async(event.GetRoleset)()
        
        for i, option in enumerate(option_preset.options):
            if option['send_notifcations'] == True:
                attendance: Attendance = await sync_to_async(event.GetAttendance)()
                mentions = ''
                if attendance.get_signup_option_count(SignupOption(i)) > 0:
                    signups = attendance.get_signup_option_list(SignupOption(i))
                    users: list[User] = await sync_to_async(User.objects.filter, thread_sensitive=True)(id__in=signups)
                    userIDs: list[int] = await sync_to_async(list)(await sync_to_async(users.values_list)('id', flat=True))
                    
                    for attendee in signups:
                        member = guild.get_member(attendee)
                        
                        if member and not member.is_bot:
                            if int(member.id) in userIDs:
                                u = await sync_to_async(GetUser)(users, userIDs.index(int(member.id)))
                                mentions += f'{member.mention}\n'
                            
                            if roleset != None and roleset.roles[i]["role_id"] != None and roleset.roles[i]["role_id"].lower() != 'none':
                                try:
                                    await evt.app.rest.remove_role_from_member(guild, int(member.id), roleset.roles[i]["role_id"])
                                except ForbiddenError:
                                    logger.warning(f'Bot does not have permission to remove role {roleset.roles[i]["role_id"]} from {member.mention} in guild {guild.id}')
                    
                    attendanceEmbd.add_field(option['label'], mentions, inline=True )
        
        try:
            threads = await evt.app.rest.fetch_active_threads(event.channel)
        except NotFoundError:
            pass
        except Exception as e:
            logger.error(f'Error fetching public archived threads: {e}')
        
        try:
            event_thread = None
            for thrd in threads:
                if thrd.id == event.thread:
                    event_thread = thrd
                    break       
            await event_thread.send(embed=attendanceEmbd)
        except Exception as e:
            logger.error(f'Error deleting event thread: {e}')
        
        try:
            if config.thread_delete_method == 1:
                await evt.app.rest.edit_channel(event.thread, archived=True)
            else:
                await evt.app.rest.delete_channel(event.thread)
        except NotFoundError:
            pass
        except ForbiddenError:
            MissingPermissionsEmbed = Embed(description=f'Bot does not have permission to delete thread for event `{event.title}`.\n You will need to manually clean up the thread, please make suer the bot has the ability to manage threads globally or in the required channels.')
            
            if config.log_channel:
                logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
                
                if logChnl and HasChannelPermission(logChnl, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
                    await logChnl.send(embed=MissingPermissionsEmbed)
                else:
                    guild.fetch_owner().send(content="You are getting this message because you have no log channel set. This is fine but you will get this message for each event failed missing permission check. This is so you understand why this is happening.", embed=MissingPermissionsEmbed)
            else:
                guild.fetch_owner().send(content="You are getting this message because you have no log channel set. This is fine but you will get this message for each event failed missing permission check. This is so you understand why this is happening.", embed=MissingPermissionsEmbed)
        except:
            logger.error(sys.exc_info())
    else:
        try:
            await evt.app.rest.delete_channel(event.thread)
        except NotFoundError:
            pass
        except ForbiddenError:
            MissingPermissionsEmbed = Embed(description=f'Bot does not have permission to delete thread for event `{event.title}`.\n You will need to manually clean up the thread, please make suer the bot has the ability to manage threads globally or in the required channels.')
            
            if config.log_channel:
                logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
                if logChnl and HasChannelPermission(logChnl, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
                    await logChnl.send(embed=Embed(description=f'Bot does not have permission to delete thread for event `{event.title}`.\n You will need to manually clean up the thread, please make suer the bot has the ability to manage threads globally or in the required channels.'))
                else:
                    guild.fetch_owner().send(content="You are getting this message because you have no log channel set. This is fine but you will get this message for each event failed missing permission check. This is so you understand why this is happening.", embed=MissingPermissionsEmbed)
            else:
                guild.fetch_owner().send(content="You are getting this message because you have no log channel set. This is fine but you will get this message for each event failed missing permission check. This is so you understand why this is happening.", embed=MissingPermissionsEmbed)
        except:
            logger.error(sys.exc_info())
    
    
    ## Google Calendar
    if config.calendar_enabled and not archive and event.calendar_event_id != None:
        try:
            cal: Calendar = Calendar()
        except:
            logger.error(sys.exc_info())
        else:   
            try:
                await sync_to_async(cal.delete_event)(event, config)
            except:
                logger.error(sys.exc_info())
    
    ## 
    # Premium Features
    ##
    if config.is_premium:
        ## Google Calendar
        try:
            sheets = Sheet(config, guild.name, event)
        except:
            logger.error(sys.exc_info())
        else:
            try:
                if archive:
                    await sheets.ArchiveSheet()
                else:
                    await sheets.DeleteSheet()
            except:
                logger.error(sys.exc_info())

    await event.async_delete()
    
    logEmbeds.append(Embed(description=f"Event Deleted - *{event.title}* <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:R>"))
    
    #LOG
    if config.log_channel:
        logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
        
        if logChnl and HasChannelPermission(logChnl, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
            if logEmbeds.__len__() > 0:
                await logChnl.send(embeds=logEmbeds)
            
    await DeleteLinkedEvents(evt.app, event, guild, archive=archive)
    
    logger.debug(f'Deleted event {evt.guild_id}, {evt.channel_id}, {evt.message_id}')

 
async def DeleteLinkedEvents(app: RESTAware, event: Events, mainGuild: GatewayGuild, archive: bool = True):
    linked_events: QuerySet[Events_Links] = await sync_to_async(Events_Links.objects.filter)(event_id=event.id)
    
    async for e in linked_events:
        e: Events_Links = e
        
        config: Config = await sync_to_async(e.Config)()
        guild = await app.rest.fetch_guild(config.guild)
        
        try:
            await app.rest.delete_message(e.channel, e.message)
        except:
            continue
        
        try:
            await sync_to_async(e.delete)()
        except:
            logger.warning(f'{sys.exc_info()}')
        
        #LOG
        if config.log_channel:
            logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
            
            if logChnl and HasChannelPermission(logChnl, guild, guild.get_my_member(), Permissions.SEND_MESSAGES):
                await logChnl.send(embed=Embed(
                                    description = f"The Event **{event.title}** hosted by **{mainGuild.name}** has been deleted."
                                ))
        
        logger.debug(f'Deleted linked event {e.id}, {e.channel}, {e.message}')


async def DeleteLinkedEvent(evt: GuildMessageDeleteEvent, event: Events_Links, config: Config):
    guild = evt.get_guild()
    
    now = arrow.utcnow()
    logEmbeds = []
    mentions = ''
    
    e: Events = await sync_to_async(event.Event)()
    archive: bool = arrow.get(e.event_date).to('utc') <= now
    
    if event.thread == None:
        logger.error(f'No thread for event {e.id}') ## CHANGE, maybe just recreat the thread and then continue but also log it in the guilds log chnanel??
        return
    
    if arrow.get(e.event_date).to('utc') <= now:
        attendanceEmbd = Embed(
            title = e.title,
            description = e.description,
            color = Color(0x228b22)
        )
        
        attendanceEmbd.add_field(name='Date', 
            value= f"<t:{int(e.event_date.timestamp())}:F>", inline=False )
        
        option_preset: Option_Presets = await sync_to_async(e.GetOptionPreset)()
        for i, option in enumerate(option_preset.options):
            if option['send_notifcations'] == True:
                attendance: Attendance = await sync_to_async(event.GetAttendance)()
                
                if attendance.get_signup_option_count(SignupOption(i)) > 0:
                    signups = attendance.get_signup_option_list(SignupOption(i))
                    users: list[User] = await sync_to_async(User.objects.filter, thread_sensitive=True)(id__in=signups)
                    userIDs: list[int] = await sync_to_async(list)(await sync_to_async(users.values_list)('id', flat=True))
                    
                    for attendee in signups:
                        member = guild.get_member(attendee)
                        if member and not member.is_bot:
                            if int(member.id) in userIDs:
                                u = await sync_to_async(GetUser)(users, userIDs.index(int(member.id)))
                                mentions += f'{member.mention}\n'
                    
                    attendanceEmbd.add_field(option['label'], mentions, inline=True )
        
        threads = await evt.app.rest.fetch_active_threads(event.channel)
        event_thread = None
        for thrd in threads:
            if thrd.id == event.thread:
                event_thread = thrd
                break       
        await event_thread.send(embed=attendanceEmbd)
        
        
        await evt.app.rest.edit_channel(event.thread, archived=True)
    else:
        await evt.app.rest.delete_channel(event.thread)
        
    # if config.is_premium:
    #     try:
    #         sheets = Sheet(config, guild.name, event)
    #     except:
    #         logger.error(sys.exc_info())
    #     else:
    #         try:
    #             if archive:
    #                 await sheets.ArchiveSheet()
    #             else:
    #                 await sheets.DeleteSheet()
    #         except:
    #             logger.error(sys.exc_info())

    await sync_to_async(event.delete)()
    
    logEmbeds.append(Embed(description=f"Event Deleted - {e.title} @ <t:{int(arrow.get(e.event_date).to('utc').datetime.timestamp())}:R>"))
    
    #LOG
    if config.log_channel:
        logChnl: GuildTextChannel = guild.get_channel(config.log_channel)
        
        if logChnl and HasChannelPermission(logChnl, guild, guild.get_my_member(), Permissions.SEND_MESSAGES) and mentions != '':
            if logEmbeds.__len__() > 0:
                await logChnl.send(embeds=logEmbeds)
    
    logger.debug(f'Deleted event {evt.guild_id}, {evt.channel_id}, {evt.message_id}')