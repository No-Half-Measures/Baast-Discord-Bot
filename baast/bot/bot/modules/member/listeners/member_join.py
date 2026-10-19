from datetime import datetime
from asgiref.sync import sync_to_async
import stripe

from django.conf import settings

from hikari import MemberCreateEvent, NotFoundError
import lightbulb

from discord.models import User

from loguru import logger


loader = lightbulb.Loader()


def GetUser(users, index):
    return users[index]

@loader.listener(MemberCreateEvent)
async def member_delete(evt: MemberCreateEvent, client: lightbulb.Client) -> None:
    if evt.guild_id != MAIN_GUILD_ID:
        return
    
    try:
        guild = await client.rest.fetch_guild(evt.guild_id)
    except NotFoundError:
        return
    except Exception as e:
        logger.warning(f"Error fetching guild {evt.guild_id}: {e}")
        return
    
    
    if guild and evt.member:
        member = await client.rest.fetch_member(evt.guild_id, evt.member.id)
        
        user, created = await sync_to_async(User.objects.get_or_create)(id=member.id, defaults={
            'avatar': member.avatar_hash if member.avatar_hash != None else 'none',
            'public_flags': member.flags,
            'flags': member.flags,
            'locale': 'en-US',
            'mfa_enabled': False,
            'discord_tag': f'{member.username}',
            'last_login': datetime.now()
        })
        
        if not created:
            if user.stripeCustomerId is not None:
                stripe.api_key = settings.STRIPE_SECRET_KEY
            
                try:
                    subscriptions = stripe.Subscription.list(customer=user.stripeCustomerId)
                except:
                    return
                else:
                    for subscription in subscriptions:
                        if subscription.status == 'active':
                            await member.add_role(941685137018609674)
                            return
            