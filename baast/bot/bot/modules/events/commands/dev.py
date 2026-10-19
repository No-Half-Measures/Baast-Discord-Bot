import sys

from asgiref.sync import sync_to_async

from hikari.errors import NotFoundError
from hikari import Guild, Permissions
from hikari.applications import ApplicationContextType as ApplicationContextType
import lightbulb

from bot.bot.utils.event_utils import BuildComponents, RebuildEventEmbed, update_other_events_messages
from app.models import Attendance_Linked, Config, Events, Attendance, Events_Links, Option_Presets

from loguru import logger


loader = lightbulb.Loader()

group = lightbulb.Group(
    name="dev",
    description="Dev Commands Group.",
    default_member_permissions=Permissions.ADMINISTRATOR,
    localize=False,
    contexts=[ApplicationContextType.GUILD],
)

loader.command(group, guilds=[MAIN_GUILD_ID])

@group.register
class DevEventRefresh(
    lightbulb.SlashCommand,
    name="event_refresh",
    description="Refresh all events.",
    localize=False,
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context, client: lightbulb.Client) -> None:
        """Event Command for Creating Events."""
        await ctx.defer(ephemeral=True)
        
        events = await sync_to_async(Events.objects.filter)(delete_date=None)
        events: list[Events] = await sync_to_async(list)(events)
        
        for event in events:
            if not event.isMarkedDelete:
                config: Config = await sync_to_async(event.Config)()
                option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
                
                try:
                    guild: Guild = await client.app.rest.fetch_guild(config.guild)
                except NotFoundError:
                    continue
                else:
                    try:
                        message = await client.app.rest.fetch_message(int(event.channel), int(event.message))
                    except NotFoundError:
                        continue
                    else:
                        mainAttendance = await sync_to_async(event.GetAttendance)()
                        
                        les = await sync_to_async(Events_Links.objects.filter)(event_id=event)
                        les = await sync_to_async(les.exclude)(linked_guild=config)
                        linkedEvents: list[Events_Links] = await sync_to_async(list)(les)
                        
                        linkedAttendances: list[Attendance_Linked] = []
                        for le in linkedEvents:
                            linkedAttendances.append(await sync_to_async(le.GetAttendance)())
                        
                        # Rebuild Event Embed
                        try:
                            eventEmbeds = await RebuildEventEmbed(client.app.rest, event, mainAttendance, linkedAttendances)
                        except:
                            logger.warning(sys.exc_info())
                        else:
                            await message.edit(embeds=eventEmbeds, components=await BuildComponents(client.app.rest, config, option_preset, event.date_arrow))
                        
                        try:
                            await update_other_events_messages(client.app.rest, event, guild)
                        except:
                            logger.warning(sys.exc_info())
                        ##
        
        await ctx.respond(content=f"Refreshed {len(events)} events", ephemeral=True)