from asyncio import sleep
from datetime import datetime, timedelta
import sys
from typing import Dict, List
import pytz
from asgiref.sync import async_to_sync, sync_to_async
import logging
import time

from django.http import HttpRequest, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache import cache

from gspread import Worksheet

# Get an instance of a logger
from loguru import logger

from channels.layers import get_channel_layer

from hikari import RESTApp, UnauthorizedError, OwnUser, TokenType

from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.enums import SignupOption

from app.models import Events, Events_Links, Config, Attendance, Attendance_Linked, Templates, Option_Presets, Stats_Deleted, Preset_Roles
from discord.hashids import Hashids
from cache.helpers import GetGuilds, GetGuild
from cache.models import DiscordGuild

from discord.OAuth2 import Guild, exchange_code, DUser, convertDiscordGuilds


CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')
AUTH_URL = getattr(settings, 'AUTH_URL')
REDIRECT_URL = getattr(settings, 'REDIRECT_URL')


@login_required(login_url="/login")
def get_authenticated_user(request: HttpRequest):
    user = request.user

#
# ADMIN
#
@sync_to_async
def getUser(request: HttpRequest):
  return request.user

@sync_to_async
def isStaff(user):
  return user.is_staff

def get_posts(tag, page=1):
  cached_data = cache.get('dash_event%s_page%s' % (tag, page))
  if not cached_data:
      cached_data = cache.get(page)
      cache.set('dash_event%s_page%s' % (tag, page), cached_data, 60)
  return cached_data

async def dash_admin_guilds(request: HttpRequest):
  user = await getUser(request)
  if not await isStaff(user):
    return redirect("/")

  access_token = await sync_to_async(request.session.get)("access_token")
  if access_token:#if token is valid
    restapp = RESTApp()
    await restapp.start()
    
    cachedGuilds: list[DiscordGuild] = list()#await sync_to_async(GetGuild)()
    
    try:
      confs: list[Config] = await sync_to_async(Config.objects.all)()
    except:
      logger.error("Error getting configs")
    else:
      async for conf in confs:
        conf: Config = conf
        
        cachedGuild: DiscordGuild = None
      
        timeout = 2   # [seconds]
        timeout_start = time.time()

        try:
          cachedGuild = await sync_to_async(GetGuild)(str(conf.gid))
        except DiscordGuild.DoesNotExist:
          response_channel_name = userid + "_cg_response"
                
          from channels.layers import get_channel_layer
          channel_layer = get_channel_layer()
          await channel_layer.send('discord', {'type': 'get.guild', 'response_channel': response_channel_name, 'id': str(conf.gid)})
          response = await channel_layer.receive(response_channel_name)

          if response['success'] == False:
            continue
          
          cachedGuild = await sync_to_async(GetGuild)(guild.id)
          cachedGuilds.append(cachedGuild)
    
    tempGuilds = await convertDiscordGuilds(cachedGuilds)
    
    context = None
    async with restapp.acquire(access_token, TokenType.BEARER) as bearer:
      try:
        user = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
      except UnauthorizedError:
        return redirect(AUTH_URL)
      
    guilds: list[DiscordGuild] = await sync_to_async(GetGuilds)()
    inactiveCnt = len(tempGuilds) - await sync_to_async(guilds.count)()
    
    premiumCount = 0
    async for conf in confs:
      if conf.delete_date is None and conf.is_premium:
        premiumCount += 1
    
    context = {
      "user" : user,
      "guilds" : tempGuilds,
      "active_guilds" : len(cachedGuilds),
      "inactive_guilds" : inactiveCnt,
      "premium_guilds" : premiumCount,
    }  
    await restapp.close()
  else:
    return redirect("/login")
  return render(request, "discord/admin/dash_admin_guilds.html", context=context)


@sync_to_async
@csrf_protect
@async_to_sync
async def admin_guild(request: HttpRequest, hashguild: str):
  access_token = await sync_to_async(request.session.get)("access_token")
  if access_token:#if token is valid
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
      hashids = Hashids(salt=SALT)
      guildid = hashids.decode(hashguild)[0]
      
      try:
        conf: Config = await sync_to_async(Config.objects.get)(guild=guildid)
      except Config.DoesNotExist:
        return JsonResponse({"error": "Invalid Guild, Has no Config"}, status=400)
      else:
        restapp = RESTApp()
        await restapp.start()
        
        cachedGuild: DiscordGuild = None
        
        timeout = 2   # [seconds]
        timeout_start = time.time()

        while time.time() < timeout_start + timeout and cachedGuild is None:
          try:
            cachedGuild = await sync_to_async(GetGuild)(conf.guild)
          except DiscordGuild.DoesNotExist:
            channel_layer = get_channel_layer()
            await channel_layer.send('discord', {'type': 'get.guild', 'id': str(conf.guild)})
            time.sleep(1)
            
        if request.method == 'GET':
          context = {
            "success": "",
            "id" : guildid,
            "name" : cachedGuild.discord_name,
            "expire_date": conf.p_expire_date
          }
          return JsonResponse(context, status=200, content_type="application/json")
        elif request.method == 'POST':
          data = request.POST.dict()

          date = data['expire_date']
          #DD/MM/YYYY
          #17:00:00 GMT 0100 (British Summer Time)
          date = date.split('/') 
          
          utc = pytz.UTC
          d = datetime(int(date[2]), int(date[1]), int(date[0]), hour=23, minute=0, tzinfo=pytz.UTC)

          if d < utc.localize( datetime.utcnow()):
            return JsonResponse({"error": "Event Date/Time can\'t be in the past! Try Again..."}, status=400)
          
          conf.p_expire_date = d

          try:
            conf.save()
          except:
            return JsonResponse({"error": "Error"}, status=400)
          else:
            return JsonResponse({"success": ""}, status=200)
  return JsonResponse({"error": "Error"}, status=400)



#
# CONFIG
#
async def buildEvent(event: Events) -> Dict:
  return {  
    "id": event.id,
    "title": event.title,
    "description": event.data['description'],
    "capacity": event.data['capacity'],
    "channel": str(event.channel),

    "event_date": event.event_date,
    #"event_date": event.event_date.tzname,
    "created_date": event.created_date,
    "recurring": event.recurring,

    "worksheet_id": event.worksheet_id,

    "sentEventReminders": event.sentEventReminders,
    "sentSignupReminders": event.sentSignupReminders,
    "sentTentativeReminders": event.sentTentativeReminders,

    "attendingCnt": event.attendingCnt(),
    "tentativeCnt": event.tentativeCnt(),
    "declinedCnt": event.declinedCnt(),

    "delete_date": event.delete_date,

    "isMarkedDelete": event.isMarkedDelete(),
    "inProgress": event.inProgress(),
    "is_upcoming": event.is_upcoming(),
    "was_published_recently": event.was_published_recently(),
  }

@sync_to_async
def buildEvents(events: List[Events]) -> List:
  lEvents = []
  for event in events:
    lEvents.append( async_to_sync(buildEvent)(event) )
  
  return lEvents

@csrf_protect
async def config_update_event_chnls(request: HttpRequest, hashguild: str, channel: str):
  access_token = await sync_to_async(request.session.get)("access_token")
  if not access_token: #if token is valid
    return JsonResponse({"error": "Not Logged In"}, status=400)

  is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
  
  if is_ajax:
    #decode
    hashids = Hashids(salt=SALT)
    guild = hashids.decode(hashguild)[0]
    
    data = request.POST.dict()
    conf: Config = await sync_to_async(Config.objects.get)(guild=guild)
    
    if request.method == "DELETE":
      if int(channel) in conf.event_channels:
        try:
          conf.event_channels.remove(int(channel))
        except:
          return JsonResponse({"error": ""}, status=400)
        else:
          await conf.asave()
          
          if conf.log_channel != 0:
            restapp = RESTApp()
            await restapp.start()
            
            async with restapp.acquire(access_token, "BEARER") as bearer:
              author: OwnUser = await bearer.fetch_my_user()
            
            await restapp.close()
            
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.send('discord', {'type': 'send.guild.log', 'channel': conf.log_channel, 'description': f'{author.mention} removed <#{channel}> from guild favorites.'})
          
          return JsonResponse({"success": ""}, status=200)
    elif request.method == "POST":
      if not int(channel) in conf.event_channels:
        try:
          conf.event_channels.append(int(channel))
        except:
          logger.warning(f'Failed to add Event channel to config')
          return JsonResponse({"error": "Failed to Add channel"}, status=400)
        else:
          await conf.asave()
          
          if conf.log_channel != 0:
            restapp = RESTApp()
            await restapp.start()
            
            async with restapp.acquire(access_token, "BEARER") as bearer:
              author: OwnUser = await bearer.fetch_my_user()
            
            await restapp.close()
            
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.send('discord', {'type': 'send.guild.log', 'channel': conf.log_channel, 'description': f'{author.mention} has add <#{channel}> to guild favorites.'})
    else:
      return JsonResponse({"error": ""}, status=400)
    return JsonResponse({"success": ""}, status=200)
  return JsonResponse({"error": ""}, status=400)


async def event_batch_delete(request: HttpRequest, hashguild: str):
  access_token = await sync_to_async(request.session.get)("access_token")
  if access_token:#if token is valid
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
      data = request.POST.dict()
      eids: List = data['eids'].split(',')

      #decode
      hashids = Hashids(salt=SALT)
      guild_id = hashids.decode(hashguild)[0]
      conf: Config = await sync_to_async(Config.objects.get)(guild=guild_id)

      restapp = RESTApp()
      await restapp.start()
      
      async with restapp.acquire(access_token, TokenType.BEARER) as bearer:
        author: OwnUser = await bearer.fetch_my_user()

      eventTitleStr = ""
      for eid in eids:
        try:
          event: Events = await sync_to_async(Events.objects.get)(gid=conf, id=eid)
        except Events.DoesNotExist:
          continue
        
        try:
          attending: Attendance = await sync_to_async(Attendance.objects.get)(id=eid)
        except:
          logger.warning(f'Event {eid} missing attendance object.')

        
        utcDate = datetime.fromtimestamp(event.event_date.timestamp(), tz=pytz.UTC)
        if utcDate <= pytz.UTC.localize(datetime.now(pytz.UTC)): 
          if attending:
            att = await sync_to_async(Attendance.objects.filter)(pk=eid)
            await sync_to_async(att.delete)()

          ev: Events = await sync_to_async(Events.objects.filter)(pk=eid)
          await ev.async_delete()
          
          # STATS
          try:
              await sync_to_async(Stats_Deleted.objects.create)(gid=conf.id, author=int(author.id), web=True)
          except:
              logger.error(sys.exc_info())
              continue
          #
        else:
          event.delete_date = event.event_date + timedelta(days=7)
          await sync_to_async(event.save)()


        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        await channel_layer.send('discord', {'type': 'delete.event', 'id': event.id, 'user_id': author.id})

        if conf.is_premium and event.worksheet_id != None:
          try:
            now = datetime.now().replace(tzinfo=pytz.UTC)
            es: EventSheet = EventSheet(event, conf)
            await es.archiveAndDeleteEventSheet(event, conf, archived=False if event.event_date > now else True)
          except:
            logger.warning(f'{sys._getframe()}:{sys.exc_info()}')

        eventTitleStr += f"{event.title} <t:{int(event.event_date.timestamp())}:R>\n "
      await restapp.close()
      
      return JsonResponse({"success": ""}, status=200)
  return JsonResponse({"error": ""}, status=400)

async def event_restore(request: HttpRequest, hashguild: str, eventid: int):
  access_token = await sync_to_async(request.session.get)("access_token")
  if access_token:#if token is valid
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
      data = request.POST.dict()
      
      restapp = RESTApp()
      await restapp.start()

      async with restapp.acquire(access_token, TokenType.BEARER) as bearer:
        author: OwnUser = await bearer.fetch_my_user()
      
      await restapp.close()
      
      #decode
      hashids = Hashids(salt=SALT)
      guildid = hashids.decode(hashguild)[0]
      conf: Config = await sync_to_async(Config.objects.get)(guild=guildid)
      
      if not conf.is_premium:
        logger.warning(f'Guild {guildid} is not a premium guild but tried to restore an event.')
        return JsonResponse({"error": ""}, status=400)
      
      event: Events = await sync_to_async(Events.objects.get)(gid=conf, id=eventid)

      reuseTemplates = data['reuseTemplates']
      restoreSignups = data['restoreSignups']
      
      template: Templates = await sync_to_async(event.GetTemplate)()
      options: Option_Presets = await sync_to_async(event.GetOptionPreset)()
      roleset: Preset_Roles = await sync_to_async(event.GetRoleset)()
      
      if not reuseTemplates:
        if data['template'] != 'undefined':
          try:
            template: Templates = await sync_to_async(Templates.objects.get)(id=data['template'])
          except Templates.DoesNotExist:
            template = None
        
        if data['option'] != 'undefined':
          try:
            options: Option_Presets = await sync_to_async(Option_Presets.objects.get)(id=data['option'])
          except Option_Presets.DoesNotExist:
            options = None
        
        if data['roleset'] != 'undefined':
          try:
            roleset: Preset_Roles = await sync_to_async(Preset_Roles.objects.get)(id=data['roleset'])
          except Preset_Roles.DoesNotExist:
            roleset = None

      if not restoreSignups:
        await sync_to_async(Attendance.objects.update_or_create)(
                id=event,
                guild=conf,
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
      
      event.delete_date = None
      
      event.template = template
      event.option_preset = options
      event.roleset = roleset
      
      await sync_to_async(event.save)()

      #
      # EVENT BUILDING
      #
      channel_layer = get_channel_layer()
      await channel_layer.send('discord', {'type': 'post.event', 
                                            'id': event.id,
                                            'user_id': int(author.id),
                                            'mentions': data['mentions'].split(','),
                                            'log': True,
                                            'is_restoration': True,
                                            'restore_signups': restoreSignups
                                            })

      #RESTOR WORKSHEETS
      if False:
        es: EventSheet = EventSheet(event, conf)
        try:
          worksheet: Worksheet = await es.CreateSheet(event, conf, messsage.make_link(guildid))
        except:
          logger.error(f'Error Creating Worksheet:\n {sys._getframe()}:{sys.exc_info()}')
        else:
          event.worksheet_id = worksheet.id
    return JsonResponse({"success": ""}, status=200)
  return JsonResponse({"error": ""}, status=400)



async def signup_delete(request: HttpRequest, hashguild: str, eventid: str, userid: str, signupoption: str):
  access_token = await sync_to_async(request.session.get)("access_token")
  
  if access_token:
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax:
      hashids = Hashids(salt=SALT)
      guildid = hashids.decode(hashguild)[0]
      
      conf: Config = await sync_to_async(Config.objects.get)(guild=guildid)
      
      ###
      restapp = RESTApp()
      await restapp.start()
      
      async with restapp.acquire(access_token, TokenType.BEARER) as bearer:
        author = await bearer.fetch_my_user()
      await restapp.close()
      ###
      
      isLinked: bool = False
      attendance: Attendance | Attendance_Linked = None

      try:
        event: Events = await sync_to_async(Events.objects.get)(gid=conf, id=int(eventid))
      except Events.DoesNotExist:
        try:
          event_linked: Events_Links = await sync_to_async(Events_Links.objects.get)(linked_guild=conf, id=int(eventid))
        except Events_Links.DoesNotExist:
          return JsonResponse({"error": "Invalid Event"}, status=400)
        else:
          isLinked = True
          
          try:
            attendance: Attendance_Linked = await sync_to_async(event_linked.GetAttendance)()
          except Attendance.DoesNotExist:
            return JsonResponse({"error": "Missing Attendance Object"}, status=400)
          except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
          
          event: Events = await sync_to_async(event_linked.Event)()
      except:
        return JsonResponse({"error": "Unowkn Error Occured"}, status=400)
      else:
        try:
          attendance: Attendance = await sync_to_async(event.GetAttendance)()
        except Attendance.DoesNotExist:
          return JsonResponse({"error": "Missing Attendance Object"}, status=400)
        except:
          logger.error(f'{sys._getframe()}:{sys.exc_info()}')
      

      try:
        await sync_to_async(attendance.remove_signup_option)(SignupOption(int(signupoption)), int(userid))
        await sync_to_async(attendance.save)()
      except:
        logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        return JsonResponse({"error": "Attendance Error"}, status=400)
      
      try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        await channel_layer.send('discord', {'type': 'remove.user.from.event', 'id': event.id if isLinked == False else event_linked.id, 'is_linked': isLinked,'user_id': userid, 'mngr_id': author.id, 'signup_index': signupoption})
        await channel_layer.send('discord', {'type': 'update.event', 'id': event.id, 'user_id': author.id, 'edits': [5], 'log': False})
        
        return JsonResponse({"success": ""}, status=200)
      except:
        logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        return JsonResponse({"error": "Channel error."}, status=400)
      
  return JsonResponse({"error": "Unkown"}, status=400)


def upload_file_ajax(request: HttpRequest):
  if request.method == 'POST':
    uploaded_file = request.FILES.get('files')
    if uploaded_file:
      #print(uploaded_file)
      return JsonResponse({'attachment': uploaded_file.name})
    else:
      return JsonResponse({'message': 'File not provided'}, status=400)
  return JsonResponse({'message': 'Invalid request'}, status=400)


#
#
#

def discord_login(request: HttpRequest):
  # login_required redirects with GET ?next=...; forms may POST next. Referer is a weak fallback.
  next_url = (
      request.POST.get('next')
      or request.GET.get('next')
      or request.META.get('HTTP_REFERER', '/')
  )
  if not next_url or not url_has_allowed_host_and_scheme(
      next_url,
      allowed_hosts={request.get_host()},
      require_https=request.is_secure(),
  ):
    next_url = '/'
  from urllib.parse import urlencode
  params = {'state': next_url}
  url = f"{AUTH_URL}&{urlencode(params)}"
  return redirect(url)
  

async def discord_redirect(request: HttpRequest):
  code = request.GET.get('code')
  state = request.GET.get('state')

  token = await exchange_code(code)
  await sync_to_async(request.session.__setitem__)("access_token", token)
  
  
  print(f'{code}:{state} - {token}')
  #
  restapp = RESTApp()
  await restapp.start()
  
  async with restapp.acquire(token, TokenType.BEARER) as client:
    try:
      user = await client.fetch_my_user()
    except:
      print(f'{sys._getframe()}:{sys.exc_info()}')
    
    discord_user = await sync_to_async(authenticate)(request, user=user)

  await restapp.close()
  #
  discord_user = list(discord_user).pop()

  await sync_to_async(login)(request, discord_user)
  # return JsonResponse({"user": user})
  
  if state and url_has_allowed_host_and_scheme(
      state,
      allowed_hosts={request.get_host()},
      require_https=request.is_secure(),
  ):
    return redirect(state)
  
  
  return redirect('/panel')


# # # # # 
def ConvertTimeFromDBToValues (dbtime: str) -> tuple[int]:
  sTime = dbtime.split(':')

  hours: int = 0
  minutes: int = 0
  seconds: int = 0

  if 'd' in sTime[0].lower():
    split_string = sTime[0].lower().split("days,", 1)
    try:
      hours = (24 * int(split_string[0]))

      if len(split_string) > 1:
        hours += int(split_string[1])
    except ValueError:
      raise ValueError
  else:
    try:
      hours = int(sTime[0])
    except ValueError:
      raise ValueError

  if len(sTime) == 2:
    try:
      minutes = int(sTime[1])
    except ValueError:
      raise ValueError
  elif len(sTime) == 3:
    try:
      seconds = int(sTime[2])
    except ValueError:
      raise ValueError

  return hours, minutes, seconds


def discord_logout(request: HttpRequest):
  logout(request)
  return redirect("/")



