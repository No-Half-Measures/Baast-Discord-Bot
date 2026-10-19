import time
import sys

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from asgiref.sync import sync_to_async
from aiohttp import web

from typing import Union

import hikari
from hikari import RESTApp
import stripe

from app.models import Config, Events
from cache.models import DiscordGuild
from discord.models import User
from discord.hashids import Hashids

from cache.helpers import GetGuilds, GetGuild, save_discord_meta_models

from channels.layers import get_channel_layer

from loguru import logger

default_icon_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"

salt = "HASH_SALT_HERE"

route_table = web.RouteTableDef()

#CACHE_TTL = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', DEFAULT_TIMEOUT)
#SALT = getattr(settings, 'HASH_SALT', None)

CLIENT_ID = getattr(settings, 'CLIENT_ID')
CLIENT_SECRET = getattr(settings, 'CLIENT_SECRET')
CLIENT_TOKEN  = getattr(settings, 'CLIENT_TOKEN')
AUTH_URL = getattr(settings, 'AUTH_URL')
REDIRECT_URL = getattr(settings, 'REDIRECT_URL')

async def exchange_code(code):
  access_token = None
  
  restapp = RESTApp()
  await restapp.start()

  async with restapp.acquire() as client:
    try:
      auth_token = await client.authorize_access_token(CLIENT_ID, CLIENT_SECRET, code, REDIRECT_URL)
    except:
      print(f'{sys._getframe()}:{sys.exc_info()}')
    else:
      access_token = auth_token.access_token

  await restapp.close()

  return access_token

@route_table.get("/")
async def oauth(self, request: web.Request):
  code = request.query.get("code")
  if not code:
    return web.json_response({"error": "'code' is not provided"}, status=400)

  token = await self.exchange_code(code)

  r = self.acquire(token, hikari.TokenType.BEARER)
  user = await r.fetch_my_user()

  return web.Response(text=str(repr(user)))
  
class Guild:
  def __init__(self, guild: hikari.OwnGuild) -> None:
    self.__guild: hikari.OwnGuild = guild

    self.__config = Config.objects.get(guild=self.__guild.id)

  def __repr__(self) -> str:
    return repr(self.__guild)

  @property
  def guild(self) -> hikari.OwnGuild:
    return self.__guild

  @property
  def user_is_administrator(self):
    return self.__guild.my_permissions == hikari.Permissions.ADMINISTRATOR
  
  @property
  def id(self):
    return int(self.__guild.id)

  @property
  def name(self):
    return str(self.__guild.name)
  
  @property
  def icon(self):
    return str(self.__guild.make_icon_url())

  @property
  def hash(self):
    hashids = Hashids(salt=salt)
    return hashids.encode(int(self.__guild.id))

  @property
  def config(self) -> Config:
    return self.__config

  @property
  def eventCount(self) -> int:
    try:
      return len(Events.objects.filter(gid=self.config.id))
    except:
      return 0


class DUser:
  def __init__(self, user : hikari.OwnUser, djangoUser : Union[AbstractBaseUser, AnonymousUser]) -> None:
    self.__user: hikari.OwnUser = user
    self.__duser: User = djangoUser

    self.__isStaff = self.__duser.is_staff

  @property
  def premium_type(self):
    types = ["Does not have", "Nitro Classic", "Nitro"]
    try:
      return types[self.__user.premium_type]
    except KeyError:
      return None

  @property
  def id(self):
    return str(self.__user.id)
  
  @property
  def avatar(self):
    return str(self.__user.make_avatar_url()) if self.__user.make_avatar_url() != None else "https://cdn.discordapp.com/embed/avatars/3.png"
  
  @property
  def is_staff(self):
    return self.__isStaff

  @property
  def username(self):
    return self.__user.username

  @property
  def notifications_enabled(self):
    return self.__duser.notifications_enabled
  
  @property
  def stripeCustomerId(self):
    return self.__duser.stripeCustomerId

  @property
  def subLocked(self):
    return self.__duser.subLocked

  @property
  def subGuilds(self):
    return self.__duser.subGuilds

  @property
  def subs(self) -> zip:
    subs = []

    for i, id in enumerate(self.__duser.subGuilds):
      subs.append({"id":id, "lock":self.__duser.subLocked[i]})

    return subs

async def convertGuilds(guilds: list[hikari.PartialGuild], userid: str):
  Jguilds = []
  hashids = Hashids(salt=salt)
  
  async for guild in guilds:
    guild: hikari.PartialGuild = guild
    cachedGuild: DiscordGuild = None
    
    try:
      cachedGuild = await sync_to_async(GetGuild)(guild.id)
    except DiscordGuild.DoesNotExist:
      response_channel_name = userid + "_cg_response"
      
      # Get Consumer to fetch Guild
      channel_layer = get_channel_layer()
      await channel_layer.send('discord', {'type': 'get.guild', 'response_channel': response_channel_name, 'id': str(guild.id)})
      response = await channel_layer.receive(response_channel_name)
      
      if response['success'] == False:
        cachedGuild, _ =  await sync_to_async(DiscordGuild.objects.update_or_create)(
          discord_id=guild.id,
          defaults={
                      "discord_name": (guild.name),
                      "discord_icon_url": (guild.make_icon_url()),
                      "discord_owner_user": 0, 
                      "discord_member_count": 0,
                      "has_app": False
                  },
        )
      else:
        try:
          cachedGuild = await sync_to_async(GetGuild)(guild.id)
        except DiscordGuild.DoesNotExist:
          logger.error(f'Error fetching guild: {guild.id}')
          continue
    
    if cachedGuild.has_app:
      try:
        conf: Config = await sync_to_async(Config.objects.get)(guild=guild.id)
      except:
        logger.error(f'Error fetching config: {guild.id}')
        continue
      
      events = await sync_to_async(Events.objects.filter)(gid=conf, delete_date=None)
      evnt_cnt = await sync_to_async(len)(events)
      
      if conf.stripeSubscriptionId != None:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        try:
          subscription: stripe.Subscription = stripe.Subscription.retrieve(conf.stripeSubscriptionId)
        except:
          logger.error(f'Error fetching subscription: {conf.stripeSubscriptionId}')
          
      
      data = {
        "name": guild.name,
        "id": int(guild.id),
        "hash": hashids.encode(int(guild.id)),
        "icon": guild.make_icon_url(),
        "event_count": evnt_cnt,
        "member_count": cachedGuild.discord_member_count,
        "event_channels": conf.event_channels if conf else [],
        "is_premium": conf.is_premium if conf else False,
        "owner_id": cachedGuild.discord_owner_user,
        "stripeSubscriptionId": conf.stripeSubscriptionId if conf else None,
        "sub_cancelled": conf.is_sub_cancelled if conf else False,
        "sub_end_date": conf.p_expire_date.strftime('%d-%m-%Y') if conf else None,
      }
      
      #
      response_channel_name = str(guild.id) + "_" + userid + "_response"
      
      channel_layer = get_channel_layer()
      await channel_layer.send('discord', {'type': 'is.event.manager', 'response_channel': response_channel_name, 'guild_id': guild.id, 'user_id': userid, 'section': 'event'})
      response = await channel_layer.receive(response_channel_name)
      #
      
      data['is_admin'] = (hikari.Permissions.ADMINISTRATOR in guild.my_permissions)
      data['is_manager'] = response['has_access']
      data['is_owner'] = str(data["owner_id"]) == userid
      
      Jguilds.append(data)
  return Jguilds

async def convertDiscordGuilds(guilds: list[DiscordGuild]):
  Jguilds = []
  hashids = Hashids(salt=salt)
  
  for g in guilds:
    guild: DiscordGuild = g
    
    if guild.has_app:
      try:
        conf: Config = await sync_to_async(Config.objects.get)(guild=guild.discord_id)
      except:
        continue
    
      events = await sync_to_async(Events.objects.filter)(gid=conf, delete_date=None)
      evnt_cnt = await sync_to_async(len)(events)
        
      data = {
        "name": guild.discord_name,
        "id": int(guild.discord_id),
        "hash": hashids.encode(int(guild.discord_id)),
        "icon": guild.discord_icon_url,
        "event_count": evnt_cnt,
        "member_count": guild.discord_member_count,
        "event_channels": conf.event_channels if conf else [],
        "is_premium": conf.is_premium if conf else False,
        "owner_id": guild.discord_owner_user
      }
      
      Jguilds.append(data)
  
  return Jguilds