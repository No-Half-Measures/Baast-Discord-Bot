from datetime import datetime
import pytz

from asgiref.sync import sync_to_async

from hikari import Activity, ActivityType, GatewayBot, Status
import lightbulb

from app.models import Events, Config


from loguru import logger

loader = lightbulb.Loader()

@loader.task(lightbulb.uniformtrigger(minutes=1))
async def presence(bot: GatewayBot) -> None:
    now = datetime.now(tz=pytz.UTC)
    stage = now.minute / 15
    
    activity = Activity(
        name=f"https://baast.app/pricing/",
        type=ActivityType.CUSTOM,
    )
    
    if stage < 1:
        activity.name = f"Monitoring {await Events.objects.acount()} Events."
    elif stage < 2:
        pconfs = await sync_to_async(Config.objects.filter)(p_expire_date__gte = now)
        
        activity.name = f"Has { await pconfs.acount()} Plus Servers."
    elif stage < 3:
        activity.name = f"In {len(bot.cache.get_guilds_view())} Servers."
    else:
        activity.name = f"Support @ https://discord.gg/RNrA9Gtxmm"
    
    if activity:
        try:
            await bot.update_presence(status=Status.ONLINE, activity=activity)
        except Exception as e:
            logger.warning(f"Error updating presence: {e}")