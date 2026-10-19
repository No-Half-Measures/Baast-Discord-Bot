import sys
import arrow
import asyncio

from asgiref.sync import sync_to_async

import lightbulb
from hikari import Embed, MessageFlag, Guild, Role, GuildTextChannel, Color, NotFoundError, Member, Permissions, PermissionOverwriteType, Message, LazyIterator, OwnGuild, errors, Emoji
from hikari.applications import ApplicationContextType as ApplicationContextType

from cache.helpers import save_discord_meta_models

from app.models import Events, Config, Option_Presets, Stats_Edited, Stats_Created, Stats_Deleted, Events_Links, Templates, Attendance, Preset_Roles, CommandAnalytics

from bot.bot.utils.enums import SignupOption
from bot.bot.components.bool_buttons import BooleanButton
from bot.bot.components.support_button import SupportButton
from bot.bot.utils.exceptions import SetupCancel, NoValues
from bot.bot.utils.discord_utils import GetChannels, GetChannels_M, GetBool, GetGuilds, GetRoles_M
from bot.bot.utils.event_utils import (GetEvent, GetTemplate, GetSignupOptions, CreateEventDB, RunEventBuilder, RebuildEventEmbed, GetRoleset)
from bot.bot.modules.events.classes.calendar import Calendar
from bot.bot.modules.events.classes.sheet import Sheet

from loguru import logger

loader = lightbulb.Loader()

group = lightbulb.Group(
    name="extensions.event.name",
    description="extensions.event.description",
    default_member_permissions=Permissions.KICK_MEMBERS,
    localize=True,
    contexts=[ApplicationContextType.GUILD],
)

loader.command(group)#, guilds=[MAIN_GUILD_ID, 781645306689093642])

@group.register
class EventCreate(
    lightbulb.SlashCommand,
    name="extensions.event_create.name",
    description="extensions.event_create.description",
    localize=True,
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Event Command for Creating Events."""
        await ctx.defer(ephemeral=True)
        
        cmd_analytics = await sync_to_async(CommandAnalytics.objects.create)(gguild=ctx.guild_id, user_id=ctx.user.id, command="event_create",
                                                                             stage="start", success=False, error=None)
        
        try:
            await save_discord_meta_models(ctx)
        except Exception as e:
            logger.error(f"EventCreate: {ctx.interaction.guild_id} - {e}")
        
    
        ###
        USER_LOCAL = ctx.interaction.locale
        ###
        
        guild: Guild = await ctx.client.rest.fetch_guild(ctx.guild_id)
        
        rsp = await ctx.respond(content=Embed(title=f'Loading Event Creation...'), ephemeral=True)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.edit_response(rsp, content="Error: Guild has not Config...")
            return
        else:
            # VARS
            data: dict = {}
            date: arrow.Arrow = arrow.utcnow()
            mentions: list[Role] = []
            
            sheetid: str = None
            mentionStr, everyone = "", False
            
            try:
                cmd_analytics.stage = "get_channels"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            try:
                channel = await GetChannels(ctx, client, snowflake=rsp, max=1, fav_channels=config.event_channels, reqNone=False)
            except (asyncio.TimeoutError, SetupCancel):
                return
            except NoValues:
                await ctx.edit_response(rsp, content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `View Channel`, `Send Messages`, `Send Messages in Threads`, `Create Public Threads`, `Mention Everyone`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
                return
            except:
                logger.error(sys.exc_info())
                return
            
            try:
                cmd_analytics.stage = "get_template"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            try:
                template = await GetTemplate(ctx, client, snowflake=rsp)
            except (asyncio.TimeoutError, SetupCancel):
                return
            except:
                logger.error(sys.exc_info())
                return
            
            try:
                cmd_analytics.stage = "get_option_preset"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            try:
                option_preset = await GetSignupOptions(ctx, client, rsp, template)
            except (asyncio.TimeoutError, SetupCancel):
                return
            except:
                logger.error(sys.exc_info())
                return
            
            try:
                cmd_analytics.stage = "get_roleset"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            roleset = None
            try:
                await sync_to_async(Preset_Roles.objects.get)(preset=option_preset)
            except Preset_Roles.DoesNotExist:
                roleset = None
            else:
                try:
                    roleset = await GetRoleset(ctx, client, rsp, option_preset)
                except (asyncio.TimeoutError, SetupCancel):
                    return
                except:
                    logger.error(sys.exc_info())
                    return
            
            #
            # START Builder
            #
            try:
                cmd_analytics.stage = "event_builder"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            try:
                data, date, recuringInterval, recuringUntil, keep_signup_data, mentions = await RunEventBuilder(ctx, client, rsp, template, option_preset, ctx.member.user, 
                                                    reccuring_events_count=await sync_to_async(Events.objects.filter(gid=config, recurring_interval__gt=0).count)())
            except (asyncio.TimeoutError, SetupCancel):
                return
            except:
                logger.error(sys.exc_info())
                return
            
            #
            # END Builder
            # 
            
            
            # Store and Build the public event Event
            try:
                cmd_analytics.stage = "create_event_db"
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            
            try:
                event, eventMsg = await CreateEventDB(ctx, client, config, guild.get_channel(channel[0]), data['color'], data['title'], data['description'], 
                                                      date, recuringInterval, recuringUntil, keep_signup_data, data['capacity'], data['thumbImage'], 
                                                      mentions, template, option_preset, roleset=roleset)
            except:
                logger.error(sys.exc_info())
                return
            
            if event == None:
                await ctx.respond(content="Event creation failed, Try again or Create a [Support Ticket](https://discord.gg/qPTFPQVbMx) if this issue persists.", 
                                  flags=MessageFlag.EPHEMERAL | MessageFlag.SUPPRESS_EMBEDS)
                return
            
            ## Google Sheet
            sheets = None
            if config.is_premium and template != None:
                try:
                    sheets = Sheet(config, guild.name)
                except:
                    logger.error(sys.exc_info())
                else:
                    try:
                        await sheets.CreateSheet(event, eventMsg.make_link(guild))
                    except:
                        logger.error(sys.exc_info())
                    else:
                        event.worksheet_id = sheets.sheet.id
                        await event.asave()
            
            ## Google Calendar
            if config.calendar_enabled and config.is_premium:     
                try:
                    cal: Calendar = Calendar()
                except:
                    logger.error(sys.exc_info())
                else:
                    #if cal != None: #config.calendar_enabled == True:
                    if config.calendar_id == None:# or cal.check_calendar_exists(config.calendar_id):
                        try:
                            await sync_to_async(cal.create_calendar)(guild, config)
                        except:
                            logger.error(sys.exc_info())
                            
                    try:
                        await sync_to_async(cal.create_event)(event, config)
                    except:
                        logger.error(sys.exc_info())
            
            
            # STATS
            try:
                await sync_to_async(Stats_Created.objects.create)(gid=config.id, author=int(ctx.user.id))
            except:
                logger.error(sys.exc_info())
            #
            
            await ctx.edit_response(rsp, content=Embed(
                title = 'Finished',
                description=f"[{data['title']} @ {date.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({eventMsg.make_link(guild.id)})",
                color = Color(0x00ff00)
            ), components=None)
            
            try:
                cmd_analytics.stage = "finished"
                cmd_analytics.success = True
                await cmd_analytics.asave()
            except:
                logger.error(sys.exc_info())
            
            if config.log_channel:
                try:
                    if config.is_premium:
                        await (await config.log(guild)).send(Embed(description=f"{ctx.user.mention} created event [{data['title']} @ {date.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({eventMsg.make_link(guild.id)})"
                                                            f"\nWith [google sheet]({sheets.sheet.url}) {sheetid}."))
                    else:
                        await (await config.log(guild)).send(Embed(description=f"{ctx.user.mention} created event [{data['title']} @ {date.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({eventMsg.make_link(guild.id)})"))
                except Exception as e:
                    logger.error(e)


        
@group.register
class EventRestore(
    lightbulb.SlashCommand,
    name="extensions.event_restore.name",
    description="extensions.event_restore.description",
    localize=True,
):

    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f'EventRestore: {ctx.guild_id}')
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)

        guild: Guild = await client.rest.fetch_guild(ctx.guild_id)
        now = arrow.utcnow()
        
        rsp_snowflake = await ctx.respond(content=Embed(title='Loading...'), ephemeral=True)
        
        # Fetch guild config
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.edit_response(rsp_snowflake, Embed(description=f"Error: There was an issue fetching the guilds config..."))
            return
        
        

        
        # If the guild is not remium then this command is disabled
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.edit_response(rsp_snowflake, Embed(description=f"This is a premium command which this guild is not of premium status."), 
                            components=[PremiumButtonRow])
            return
        
        # Fetch all events that are deleted
        events = await sync_to_async(Events.objects.filter)(gid=config, delete_date__gte = now.datetime)

        if not await sync_to_async(events.exists)():
            await ctx.edit_response(rsp_snowflake, Embed(description=f"There are no events that can be restored."))
            return
        
        # Select
        try:
            event: Events = await GetEvent(ctx, client, rsp_snowflake, await sync_to_async(list)(events), title="What event do you wish to restore?")
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        # Channel to send to
        try:
            channel = await GetChannels(ctx, client, rsp_snowflake, max=1, fav_channels=config.event_channels)
        except asyncio.TimeoutError or SetupCancel:
            return
        except NoValues:
            await ctx.edit_response(rsp_snowflake, content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `SEND_MESSAGES`, `SEND_MESSAGES_IN_THREADS`, `VIEW_CHANNEL`, `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, `MANAGE_THREADS`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
            return
        except:
            logger.error(sys.exc_info())
            return
        
        # Get Template and Signup Options Preset
        template = await sync_to_async(event.GetTemplate)()    
        option_preset = await sync_to_async(event.GetOptionPreset)()
        roleset = await sync_to_async(event.GetRoleset)()
        
        # Resuse Template?
        try:
            new_template = await GetBool(ctx, client, rsp_snowflake, description=f"""Do you want to use the existing template and options?
                                         \n**Template:** `{template.name}`
                                         \n**options:** `{option_preset.name}`
                                         \n**roleset:** `{roleset.name if roleset != None else 'None'}`
                                        \n*WARNING: This will delete the existing signups if you change the template, options or roleset.*""")
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        # Restore Signups?
        restore_signups = False
        if new_template:
            try:
                restore_signups = await GetBool(ctx, client, rsp_snowflake, description="Do you want to restore peoples signups?")
            except asyncio.TimeoutError or SetupCancel:
                return
            except:
                logger.error(sys.exc_info())
                return
        
        # If no template or signup options preset or the user would like to change them, fetch them from the user
        if not new_template or template == None or option_preset == None:
            try:
                template = await GetTemplate(ctx, client, rsp_snowflake)
            except asyncio.TimeoutError or SetupCancel:
                return
            except:
                logger.error(sys.exc_info())
                return
            
            try:
                option_preset = await GetSignupOptions(ctx, client, rsp_snowflake, template)
            except asyncio.TimeoutError or SetupCancel:
                return
            except:
                logger.error(sys.exc_info())
                return
            
            try:
                roleset = await GetRoleset(ctx, client, rsp_snowflake, option_preset)
            except asyncio.TimeoutError or SetupCancel:
                return
            except:
                logger.error(sys.exc_info())
                return
        
        #
        # START Builder
        # 
        
        try:
            data, date, recuringInterval, recuringUntil, keep_signup_data, mentions = await RunEventBuilder(ctx, client, rsp_snowflake, template, option_preset, ctx.member.user, event=event)
        except (asyncio.TimeoutError, SetupCancel):
            return
        except:
            logger.error(sys.exc_info())
            return
        
        #
        # END Builder
        # 
        
        
        # Fetch and restore events attendance
        try:
            attendance = await sync_to_async(Attendance.objects.get)(id=event)
        except Attendance.DoesNotExist:
            await sync_to_async(Attendance.objects.update_or_create)(
                    id=event,
                    guild=config,
                    defaults={
                        "option_1": [],
                        "option_2": [],
                        "option_3": [],
                        "option_4": [],
                        "option_5": [],
                        "option_6": [],
                        "option_7": [],
                        "option_8": [],
                        "option_9": [],
                    }
                )
            
            ctx.respond(Embed(description=f"Warning: There was an issue fetching the attendance record...\nBecause of this a new attendance record will be made."), ephemeral=True)
        except:
            logger.error(sys.exc_info())
        else:
            if restore_signups == False:
                await sync_to_async(Attendance.objects.update_or_create)(
                    id=event,
                    guild=config,
                    defaults={
                        "option_1": [],
                        "option_2": [],
                        "option_3": [],
                        "option_4": [],
                        "option_5": [],
                        "option_6": [],
                        "option_7": [],
                        "option_8": [],
                        "option_9": [],
                    }
                )
        
        # Update the Event data in the DB (funciton name is misleading as it also updates events)
        try:
            event, eventMsg = await CreateEventDB(ctx, client, config, guild.get_channel(channel[0]), event.color, event.title, event.description, 
                                                  date, recuringInterval, recuringUntil, keep_signup_data, event.capacity, 
                                                  event.image, mentions, template, option_preset, roleset=roleset, evntid=event.id)
        except:
            logger.error(sys.exc_info())
        
        # Build the Event Embed with existing signups if restore_signups is true
        if restore_signups:
            try:
                eventEmbeds = await RebuildEventEmbed(client.rest, event, attendance)
                await eventMsg.edit(embeds=eventEmbeds)
            except:
                logger.error(sys.exc_info())
            
            
            roleset = await sync_to_async(event.GetRoleset)()
            if roleset != None:
                for i, option in enumerate(option_preset.options):
                    attendance: Attendance = await sync_to_async(event.GetAttendance)()
                
                    signups = attendance.get_signup_option_list(SignupOption(i))
                    
                    for attendee in signups:
                        try:
                            await client.rest.add_role_to_member(guild, int(attendee), roleset.roles[i]["role_id"])
                        except errors.ForbiddenError:
                            logger.warning(f'Bot does not have permission to add role {roleset.roles[i]["role_id"]} to {attendee} in guild {guild.id}')

        
        # Check if the event is valid else error
        if event == None:
            await  ctx.edit_response(rsp_snowflake, embed="Event restoration failed, Try again or Create a [Support Ticket](https://discord.gg/qPTFPQVbMx).")
            return
        
        # Premium Features
        if config.is_premium and template != None:
            try:
                sheets = Sheet(config, guild.name, event)
            except:
                logger.error(sys.exc_info())
            
            try:
                await sheets.CreateSheet(event, eventMsg.make_link(guild))
            except:
                logger.error(f'Error Creating Worksheet:\n {sys._getframe()}:{sys.exc_info()}')
            else:
                event.worksheet_id = sheets.sheet.id
                await event.asave()
        
            try:
                await  ctx.edit_response(rsp_snowflake, Embed(description=f"You restored event [{data['title']} @ {date.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({eventMsg.make_link(guild.id)})"
                                                f"\nWith [google sheet]({sheets.sheet.url})."), components=None)
            except:
                logger.error(sys.exc_info())
        else:
            try:
                await  ctx.edit_response(rsp_snowflake, Embed(
                    description=f"You restored event [{data['title']} @ {date.format('ddd MMM Do, YYYY @ h:mm A')} UTC]({eventMsg.make_link(guild.id)})"
                ), components=None)
            except:
                logger.error(sys.exc_info())
        
        
        if config.calendar_enabled and config.is_premium:
            try:
                cal: Calendar = Calendar()
            except:
                logger.error(sys.exc_info())
            else:
                if config.calendar_id == None or not cal.check_calendar_exists(config.calendar_id):
                    try:
                        await sync_to_async(cal.create_calendar)(guild, config)
                    except:
                        logger.error(sys.exc_info())
                        
                try:
                    await sync_to_async(cal.create_event)(event, config)
                except:
                    logger.error(sys.exc_info())
        
        #LOG
        if config.log_channel:
            await (await config.log(guild)).send(embed=Embed(description=f"{ctx.user.mention} restored event [{event.title}]({eventMsg.make_link(guild.id)}) <t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>"))



@group.register
class EventInfo(
    lightbulb.SlashCommand,
    name="extensions.event_info.name",
    description="extensions.event_info.description",
    localize=True,
):
    raw = lightbulb.boolean("no_responce_to_string", "No responce users as a string.", default=False)
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f'EventInfo: {ctx.guild_id}')
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild: Guild = await client.rest.fetch_guild(ctx.guild_id)
        rsp_snowflake = await ctx.respond(content=Embed(title='Loading...'), ephemeral=True)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.edit_response(rsp_snowflake, Embed(description=f"Error: There was an issue fetching the guilds config..."))
            return
        
        events = await sync_to_async(Events.objects.filter)(gid=config, delete_date = None)

        if not await sync_to_async(events.exists)():
            await ctx.edit_response(rsp_snowflake, Embed(description=f"No events found."))
            return

        # Select
        try:
            event: Events = await GetEvent(ctx, client, rsp_snowflake, await sync_to_async(list)(events), title="Select an Event?")
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        eventsEmbed = Embed(
            title = f'{event.title} - Event Info',
            description=None,
            color = Color(0xFF7900)
        )
        eventsEmbed.set_footer(text='Event:Info')

        eventsEmbed.add_field(name='In:', value=f"<t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:R>\n", inline=False)
        
        # Data
        template: Templates = await sync_to_async(event.GetTemplate)()
        option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        attendance: Attendance = await sync_to_async(event.GetAttendance)()
        
        
        # Channel
        try:
            channel: GuildTextChannel = await client.rest.fetch_channel(event.channel)
        except NotFoundError:
            logger.warning(f'Channel not found for event {event.id} and is not marked for deletion!')
        except:
            logger.error(sys.exc_info())
            
            
        members: list[Member] = []
        memberIDs: list[int] = []
        try:
            for id in channel.permission_overwrites:
                if Permissions.VIEW_CHANNEL in channel.permission_overwrites[id].allow:
                    if PermissionOverwriteType.MEMBER == channel.permission_overwrites[id].type.value:
                        member = guild.get_member(id)

                        if member not in members and not member.is_bot:
                            if not attendance.isAnySignupOption(int(member.id)):
                                members.append(member)
                                memberIDs.append(int(member.id))
                                
                    elif PermissionOverwriteType.ROLE == channel.permission_overwrites[id].type.value:
                        role = guild.get_role(id)
                        async for m in client.rest.fetch_members(ctx.guild_id):
                            if role.id in m.role_ids:
                                if m not in members and not m.is_bot:
                                    if not attendance.isAnySignupOption(int(member.id)):
                                        members.append(m)
                                        memberIDs.append(int(member.id))
        except:
            logger.critical(sys.exc_info())

        
        mentions = ''
        
        if len(members) > 0:
            for m in members:
                mentions += f'<@{m.id}>, ' if self.raw == True else f'{m.mention}, '
        else:
            mentions += 'None'
            
        eventsEmbed.add_field(name='No Responce:', value=f"{'```' if self.raw else ''}{mentions}{'```' if self.raw else ''}", inline=False)
        eventsEmbed.add_field(name='Check-In:', value=f"{'Sent' if event.sentCheckin else 'Not Sent'}", inline=True)
        
        for i, r in enumerate(config.reminders):
            eventsEmbed.add_field(name=f'{r["name"]}:', value=f"{'Sent' if event.sentReminders[i] else 'Not Sent'}", inline=True)
        
        await ctx.edit_response(rsp_snowflake, eventsEmbed, components=None)
        
        
@group.register
class EventShare(
    lightbulb.SlashCommand,
    name="extensions.event_share.name",
    description="extensions.event_share.description",
    localize=True,
    hooks=[]
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f'EventShare: {ctx.guild_id}')
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
    
        guild: Guild = await client.rest.fetch_guild(ctx.guild_id)
        rsp_snowflake = await ctx.respond(content=Embed(title='Loading...'), ephemeral=True)
        
        #DB
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.edit_response(rsp_snowflake, Embed(description=f"Error: There was an issue fetching the guilds config..."))
            return


        # If the guild is not remium then this command is disabled
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.edit_response(rsp_snowflake, Embed(description=f"This is a premium command which this guild is not of premium status."), 
                            components=[PremiumButtonRow])
            return



        events = await sync_to_async(Events.objects.filter)(gid=config, delete_date = None)

        if not await sync_to_async(events.exists)():
            await ctx.edit_response(rsp_snowflake, Embed(description=f"No events found."))
            return
        
        # Select
        try:
            event: Events = await GetEvent(ctx, client, rsp_snowflake, await sync_to_async(list)(events), title="Select an Event?")
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            template: Templates = await sync_to_async(event.GetTemplate)()
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        
        # Guild Prep
        await ctx.edit_response(rsp_snowflake, Embed(description="Please wait... Loading guilds you can share too."), component=None)

        # Guild Select
        try:
            selectedGuildsIDs = await GetGuilds(ctx, client, rsp_snowflake, user=ctx.user)
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        selectedGuildID = selectedGuildsIDs[0]
        
        # Fetch Guild
        try:
            linkedGuild = await ctx.client.rest.fetch_guild(int(selectedGuildID))
        except:
            logger.error(sys.exc_info())
            return

        # Fetch Linked Config
        try:
            linkedConfig: Config = await sync_to_async(Config.objects.get)(guild=int(linkedGuild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {linkedGuild.name}:{linkedGuild.id} Doesnt have a config!')
            await ctx.edit_response(rsp_snowflake, Embed(description=f"Error: The other Guild has no Config..."), component=None)
            return
        
        # Check if already linked
        try:
            el: Events_Links = await sync_to_async(Events_Links.objects.get)(id=int(event.id), linked_guild=linkedConfig)
        except Events_Links.DoesNotExist:
            pass
        else:
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"Guild `{linkedGuild.name}` already has the event `{event.title}` shared."), component=None)
        
        # Get Log Channel for Linked Guild
        linkedLogChnl = await linkedConfig.log(linkedGuild)
        
        # Check if log channel is valid
        if linkedConfig.log_channel == None or linkedLogChnl == None:
            return await ctx.edit_response(rsp_snowflake, Embed(description="Guild doesn't have a log channel setup in order to accept this event share request."), components=None)
        
        # Tel the user to wait for guilds responce
        await ctx.edit_response(rsp_snowflake, Embed(title='Waiting for guilds responce...'), component=None)
        
        # Build Emebed
        eventEmbed = Embed(
            title = event.title,
            description = event.description,
            color = Color(0x228b22)
        )
        eventEmbed.add_field(name='Date', value= f"<t:{int(arrow.get(event.event_date).to('utc').datetime.timestamp())}:F>", inline=False )

        if template:
            eventEmbed.set_footer(text=f"{template.name}", icon=template.thumb)
        
        ## CUSTOM BOOL BUTTONS
        try:
            selectObj:BooleanButton = BooleanButton(true_lable="Accept", false_label="Decline")
            linkedMessage: Message = await client.rest.create_message(linkedLogChnl, f"{ctx.user.mention} is sharing the following:", embed=eventEmbed, components=selectObj)
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            await selectObj.attach(ctx.client, timeout=120)
        except asyncio.TimeoutError:
            await linkedMessage.edit(Embed(
                                        title = None,
                                        description = 'You took too long to respond thus the command timedout.',
                                        color = Color(0xff0000)
                                    ), components=None)
            return
        except:
            logger.error(sys.exc_info())
            return
        
        guildAccepted = selectObj.value
        
        
        # Check if guild declined
        if not guildAccepted:
            await linkedMessage.edit(Embed(description=f"You have Decline the request to share the event `{event.title}`."), components=None)
            await ctx.edit_response(rsp_snowflake, Embed(description=f"The Guild `{linkedGuild.name}` declined the request to share the event `{event.title}`."), component=None)
            return
        
        await linkedMessage.edit(embed=Embed(description=f"You have accepted the request to share the event `{event.title}`."), components=None)
        
        
        try:
            channels = await GetChannels_M(linkedMessage, linkedGuild, client, max=1, fav_channels=config.event_channels)
        except IndexError:
            pass
        except asyncio.TimeoutError or SetupCancel:
            await ctx.edit_response(rsp_snowflake, Embed(description="The other guild took too long to respond thus the command timedout."), components=None)
            return
        except NoValues:
            await ctx.edit_response(rsp_snowflake, content=Embed(title="No Accessible Channels", description="""The bot does not have access to any channels in this guild.\n
                                                           \n**Permissions:** `SEND_MESSAGES`, `SEND_MESSAGES_IN_THREADS`, `VIEW_CHANNEL`, `CREATE_PUBLIC_THREADS`, `CREATE_PRIVATE_THREADS`, `MANAGE_THREADS`""",
                                                           color=Color(0xff0000)),
                              components=SupportButton())
            return
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            mentions = await GetRoles_M(linkedMessage, linkedGuild, client)
        except asyncio.TimeoutError or SetupCancel:
            await ctx.edit_response(rsp_snowflake, Embed(description="The other guild took too long to respond thus the command timedout."), components=None)
            return
        except IndexError:
            pass
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            template = await sync_to_async(event.GetTemplate)()
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            option_preset = await sync_to_async(event.GetOptionPreset)()
        except:
            logger.error(sys.exc_info())
            return
        
        try:
            evt, eventMsg = await CreateEventDB(ctx, client, linkedConfig, linkedGuild.get_channel(channels[0]), event.color, event.title, event.description, 
                                            event.date_arrow, event.recurring_interval, event.recurring_until, event.keep_signup_data, 
                                            event.capacity, event.image, mentions, template, option_preset, linked=True, evntid=event.id)
        except:
            logger.error(sys.exc_info())
            await linkedMessage.edit(Embed(title=f'An error occured creating the event.'), components=None)
            await ctx.edit_response(rsp_snowflake, Embed(title=f'An error occured creating the event.'), components=None)
            return
        
        await linkedMessage.edit(Embed(description=f'Shared event created.'), components=None)
        await ctx.edit_response(rsp_snowflake, Embed(description=f"The Guild `{linkedGuild.name}` accepted the request to share the event `{event.title}`.", color = Color(0xf3df73)), components=None)
        
        
        ## Create a Google Calendar Event
        if linkedConfig.calendar_enabled and linkedConfig.is_premium:
            try:
                cal: Calendar = Calendar()
            except:
                logger.error(sys.exc_info())
            else:
                if linkedConfig.calendar_id == None or not cal.check_calendar_exists(linkedConfig.calendar_id):
                    try:
                        await sync_to_async(cal.create_calendar)(linkedGuild, linkedConfig)
                    except:
                        logger.error(sys.exc_info())
                        
                try:
                    await sync_to_async(cal.create_event)(event, linkedConfig, linkedEvent=evt)
                except:
                    logger.error(sys.exc_info())
        
        if config.log_channel:
            await (await config.log(guild)).send(embed=Embed(description=f"{ctx.user.mention} shared the event `{event.title}` with guild `{linkedGuild.name}`."))
        
    
@group.register
class EventUnshare(
    lightbulb.SlashCommand,
    name="extensions.event_unshare.name",
    description="extensions.event_unshare.description",
    localize=True,
    hooks=[]
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        logger.info(f'EventUnshare: {ctx.guild_id}')
        await ctx.defer(ephemeral=True)
        
        await save_discord_meta_models(ctx)
        
        guild: Guild = await client.rest.fetch_guild(ctx.guild_id)
        rsp_snowflake = await ctx.respond(content=Embed(title='Loading...'), ephemeral=True)
        
        # Guilds Config
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=int(guild.id))
        except Config.DoesNotExist:
            logger.error(f'Guild {guild.name}:{guild.id} Doesnt have a config!')
            ctx.edit_response(rsp_snowflake, Embed(description=f"Error: There was an issue fetching the guilds config..."))
            return

        # If the guild is not remium then this command is disabled
        if not config.is_premium:
            from bot.bot.components.premium_button import PremiumButtonRow
            await ctx.edit_response(rsp_snowflake, Embed(description=f"This is a premium command which this guild is not of premium status."), 
                            components=[PremiumButtonRow])
            return


        
        # Fetch Events
        events = await sync_to_async(Events.objects.filter)(gid=config, delete_date = None)
        events_ = await sync_to_async(list)(events)
        
        linked_events: list[Events] = []
        
        for e in events_:
            try:
                els = await sync_to_async(Events_Links.objects.filter)(event_id=e)
            except Events_Links.DoesNotExist:
                continue
            else:
                if await sync_to_async(els.exists)():
                    linked_events.append(e)
        
        if linked_events.__len__() == 0:
            await ctx.edit_response(rsp_snowflake, Embed(description=f"No events found that can be unshared."))
            return
        
        # Select
        try:
            event: Events = await GetEvent(ctx, client, rsp_snowflake, linked_events, title="What Event do you want to remove a link from?")
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return
        
        # Guild Prep
        await ctx.edit_response(rsp_snowflake, Embed(description="Please wait... Loading guilds..."), component=None)

        # Filter Guilds to ones only with a linked event
        myGuilds: LazyIterator[OwnGuild] = ctx.client.rest.fetch_my_guilds()
        filtered_guilds: list[OwnGuild] = []

        try:
            els: Events_Links = await sync_to_async(Events_Links.objects.filter)(event_id=event)
        except Events_Links.DoesNotExist:
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"Event `{event.title}` has no guilds shared with it."), components=None)
        
        try:
            async for g in myGuilds:
                if g.id != guild.id:
                    async for el in els:
                        el: Events_Links = el
                        cf: Config = await sync_to_async(el.Config)()

                        if int(g.id) == cf.guild:
                            filtered_guilds.append(g)
        except:
            logger.error(sys.exc_info())
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"An error occured. If this persists please report this on our [Support Server](https://discord.gg/RNrA9Gtxmm).", components=None))
        

        
        
        # Guild Select
        try:
            selectedGuildsIDs = await GetGuilds(ctx, client, rsp_snowflake, user=ctx.user, custom_list=filtered_guilds,
                                                title=f'Select the guild to unshare the event `{event.title}` from:')
        except asyncio.TimeoutError or SetupCancel:
            return
        except:
            logger.error(sys.exc_info())
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"An error occured. If this persists please report this on our [Support Server](https://discord.gg/RNrA9Gtxmm).", components=None))
        
        selectedGuildID = selectedGuildsIDs[0]
        linkedGuild: Guild = await client.rest.fetch_guild(selectedGuildID)
        
        # Get Shared Guilds Config
        try:
            linkedConf: Config = await sync_to_async(Config.objects.get)(guild=int(selectedGuildID))
            linkedEvent: Events_Links = await sync_to_async(Events_Links.objects.get)(event_id=event, linked_guild=linkedConf)
        except:
            logger.error(sys.exc_info())
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"An error occured. If this persists please report this on our [Support Server](https://discord.gg/RNrA9Gtxmm).", components=None))        
        
        # Delete the Discord Message
        try:
            message: Message = await client.rest.fetch_message(linkedEvent.channel, linkedEvent.message)
            await message.delete()
        except:
            logger.error(sys.exc_info())
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"An error occured. If this persists please report this on our [Support Server](https://discord.gg/RNrA9Gtxmm).", components=None))
        
        
        # Delete the event from the database
        try:
            await linkedEvent.adelete()
        except:
            logger.error(sys.exc_info())
            return await ctx.edit_response(rsp_snowflake, Embed(description=f"An error occured. If this persists please report this on our [Support Server](https://discord.gg/RNrA9Gtxmm).", components=None))
        
        
        await ctx.edit_response(rsp_snowflake, Embed(description=f"Event `{event.title}` is no longer shared with guild `{linkedGuild.name}`."), components=None)
        
        
        ## Create a Google Calendar Event
        if linkedConf.calendar_enabled or linkedEvent.calendar_event_id != None and linkedConf.is_premium:
            try:
                cal: Calendar = Calendar()
            except:
                logger.error(sys.exc_info())
            else:
                if linkedConf.calendar_id != None and cal.check_calendar_exists(linkedConf.calendar_id): 
                    try:
                        await sync_to_async(cal.delete_event)(linkedEvent, linkedConf)
                    except:
                        logger.error(sys.exc_info())
        
        
        if config.log_channel:
            await (await config.log(guild)).send(embed=Embed(description=f"{ctx.user.mention} has unlinked the event `{event.title}` from guild `{linkedGuild.name}`."))
        if linkedConf.log_channel:
            await (await linkedConf.log(linkedGuild)).send(embed=Embed(description=f"`{guild.name}` has unlinked the event `{event.title}` from your guild."))