from asgiref.sync import sync_to_async

from hikari import ForbiddenError, MemberDeleteEvent, NotFoundError
import lightbulb

from cache.helpers import save_discord_meta_models

from django.db.models import QuerySet

from app.models import Events, Config, Option_Presets, Attendance
from bot.bot.utils.event_utils import RebuildEventEmbed
from bot.bot.utils.enums import SignupOption

from loguru import logger


loader = lightbulb.Loader()


def GetUser(users, index):
    return users[index]

@loader.listener(MemberDeleteEvent)
async def member_delete(evt: MemberDeleteEvent, client: lightbulb.Client) -> None:
    try:
        guild = await client.rest.fetch_guild(evt.guild_id)
    except NotFoundError:
        return
    except Exception as e:
        logger.warning(f"Error fetching guild {evt.guild_id}: {e}")
        return
    
    if not guild:
        return
    
    await save_discord_meta_models(guild)
    
    if evt.user.is_bot:# and event.user.id != log.client.get_me().id:
        return
    
    config: Config = await sync_to_async(Config.objects.get)(guild = int(guild.id))
    user_id = int(evt.user.id)
    
    if not user_id:
        return

    try:
        events: QuerySet = await sync_to_async(Events.objects.filter)(gid=config)
    except Events.DoesNotExist:
        return#await interaction.create_initial_response(response_type=ResponseType.DEFERRED_MESSAGE_UPDATE)
    else:
        if events == None:
            return
    
    events: list[Events] = await sync_to_async(list)(events)
    if len(events) > 0:
        for event in events:
            option_preset: Option_Presets = await sync_to_async(event.GetOptionPreset)()
            for i, option in enumerate(option_preset.options):
                if option['send_notifcations'] == True:
                    attendance: Attendance = await sync_to_async(event.GetAttendance)()
                    
                    if attendance.isSignupOption(SignupOption(i), user_id):
                        await sync_to_async(attendance.remove_signup_option)(SignupOption(i), user_id)
            
            try:
                await evt.app.rest.remove_thread_member(event.thread, user_id)
            except NotFoundError:
                logger.warning(f'Thread {event.thread} not found')
            except ForbiddenError:
                logger.warning(f'Bot does not have permission to remove thread member {user_id} from thread {event.thread}')
            except Exception as e:
                logger.error(f'Error removing thread member {user_id} from thread {event.thread}: {e}')
            
            emmbeds = await RebuildEventEmbed(evt.app.rest, event, attendance)
            
            await evt.app.rest.edit_message(event.channel, event.message, embeds=emmbeds)
            