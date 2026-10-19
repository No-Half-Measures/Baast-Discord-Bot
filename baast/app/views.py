from datetime import datetime
import sys
import pytz
from asgiref.sync import async_to_sync, sync_to_async
import asyncio
import logging

from cache.models import DiscordGuild, DiscordUser
from cache.helpers import GetGuilds

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.conf import settings
from django.views.generic.base import TemplateView
from django.utils.decorators import classonlymethod, method_decorator
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator

from app.models import Events, Config, Blog

from discord.models import User
from discord.pages.overview_view import OverView

from hikari import NotFoundError, RESTApp, UnauthorizedError

from discord.OAuth2 import DUser, convertGuilds

import stripe

from django.conf import settings
AUTH_URL = getattr(settings, 'AUTH_URL')

from loguru import logger

@sync_to_async
def get_event_count():
    return Events.objects.filter(delete_date=None).count()

async def IndexView(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    context = None
    if access_token:#if token is valid
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as client:
            context = {
                "user" :await sync_to_async(DUser)(await client.fetch_my_user(), request.user)
            }

        await restapp.close()
    else:
        context = {
            "user" :'none'
            }
    
   
    config_guilds = await sync_to_async(Config.objects.all)()
    
    active_guilds = await sync_to_async(config_guilds.filter)(delete_date =None)
    premium_guilds = await sync_to_async(config_guilds.filter)(p_expire_date__gte = datetime.now(tz=pytz.UTC))
    
    events = await sync_to_async(Events.objects.filter)(delete_date=None)
    responce_cnt = await sync_to_async(OverView.getTotalResponceCnt)(events)

    context['responce_cnt'] = responce_cnt
    context['event_cnt'] = len(events)
    context['premium_cnt'] = await sync_to_async(premium_guilds.count)()
    context['guild_cnt'] = await sync_to_async(active_guilds.count)()
    
    posts = await sync_to_async(Blog.objects.filter)(is_published=True)
    posts = await sync_to_async(posts.order_by)('-created_at')
    posts = await sync_to_async(list)(posts)
    context['recent_posts'] = posts[:1]


    return render(request, "app/index.html", context=context)

async def PricingView(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    context = None
    if access_token:#if token is valid
        customer, user = None, None
        
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except:
                logout(request)
                return redirect(reverse('events:pricing'))
        await restapp.close()

        subscriptions = None
        if user.stripeCustomerId:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                subscriptions = stripe.Subscription.list(customer=user.stripeCustomerId)
                subscriptions = [sub.id for sub in subscriptions]
            except:
                subscriptions = None
                
        guilds, user = await get_user_guilds(request)

        context = {
            "user" : user,
            "guilds" : guilds,
            "subscriptions": subscriptions
        }
    else:
        context = {
            "user" :'none'
        }
    return render(request, "app/pricing.html", context=context)

async def FAQ(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    
    if access_token:#if token is valid
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except:
                logout(request)
                return redirect(reverse('events:faq'))
            
        await restapp.close()
    else:
        user = None
        
    return render(request, "app/faq.html", context={
            "user" :'none' if user == None else user
        })
    
async def TOS(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    if access_token:#if token is valid
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except:
                logout(request)
                return redirect(reverse('events:tos'))
            
        await restapp.close()
    else:
        user = None

    return render(request, "app/tos.html", context={
            "user" :'none' if user == None else user
        })

async def Privacy(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    if access_token:#if token is valid
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except:
                logout(request)
                return redirect(reverse('events:pricing'))
            
        await restapp.close()
    else:
        user = None

    return render(request, "app/privacy.html", context={
            "user" :'none' if user == None else user
        })
    
async def ManageSub(request: HttpRequest):
    access_token = await sync_to_async(request.session.get)("access_token")
    
    restapp = RESTApp()
    await restapp.start()
    
    async with restapp.acquire(access_token, "BEARER") as bearer:
        try:
            user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
        except UnauthorizedError:
            print("unauth")
            return redirect(AUTH_URL)
    
    await restapp.close()
    
    
    # Set your secret key. Remember to switch to your live secret key in production.
    # See your keys here: https://dashboard.stripe.com/apikeys
    if user.stripeCustomerId != None:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        billing_session = stripe.billing_portal.Session.create(
            customer=user.stripeCustomerId,
            return_url="https://baast.app/panel/user/",  # Your return URL after the user leaves the billing portal
        )
    
    # Redirect the user to the Stripe billing portal URL
    return redirect(billing_session.url if user.stripeCustomerId != None else "https://baast.app/pricing")



# Using Django
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_ENDPOINT_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    
    
    session = event['data']['object']
    customer_id = session['customer']
    subscription_id = session['subscription']
    
    if event['type'] == 'checkout.session.completed':
        guild_id = session['metadata']['guild_id']
        user_id = session['metadata']['user_id']
        
        logger.info(DiscordUser.objects.get(id=user_id).name + ' just added a subscription for ' + DiscordGuild.objects.get(id=guild_id).discord_name)
        
        try:
            User.objects.filter(id=user_id).update(stripeCustomerId=customer_id)
        except:
            return HttpResponse(status=400)
        
        try:
            Config.objects.update_or_create(
                guild=guild_id,
                defaults={
                    'stripeSubscriptionId': subscription_id,
                    'p_expire_date': datetime.fromtimestamp(session['expires_at'])
                }
            )
        except:
            logger.error(sys.exc_info())
            return HttpResponse(status=400)
        
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)('discord', {'type': 'assign.plus.role', 'member_id': user_id, 'assign': True})
        except:
            return HttpResponse(status=400)
        
    elif event['type'] == 'invoice.payment_succeeded':
        try:
            print(session['metadata'])
            config = Config.objects.get(stripeSubscriptionId=subscription_id)
            config.p_expire_date = datetime.fromtimestamp(session['period_end'])
            config.save()
        except:
            logger.error(sys.exc_info())
            return HttpResponse(status=400)
        
        logger.info('Subscription continued for ' + DiscordGuild.objects.get(discord_id=config.guild).discord_name)        
    elif event['type'] == 'customer.subscription.deleted':
        default = Config().reminders

        config: Config = Config.objects.get(stripeSubscriptionId=subscription_id)
        config.backup_reminders = config.reminders
        config.reminders = default
        config.save()
        
        
        try:
            user = User.objects.get(stripeCustomerId=customer_id)
        except:
            return HttpResponse(status=400)
        
        
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.send)('discord', {'type': 'assign.plus.role', 'member_id': user.id, 'assign': False})
        except:
            return HttpResponse(status=400)

        logger.info(DiscordGuild.objects.get(discord_id=config.guild).discord_name + ' ended their subscription.')
    else:
        logger.warning(f'Recived Stripe Event: {event["type"]} for customer {customer_id} with subscription {subscription_id}') # Just so i can be aware of unhandled events if there are any

    return HttpResponse(status=200)
    

class SuccessView(TemplateView):
    template_name = 'app/success.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        access_token = await sync_to_async(request.session.get)("access_token")
        if not access_token: #if token is valid
            return redirect("/login")

        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except UnauthorizedError:
                print("unauth")
                return redirect(AUTH_URL)

        await restapp.close()
        
        session_id = request.GET.get("session_id",None)
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout: stripe.checkout.Session = stripe.checkout.Session.retrieve(session_id)

        #customer: stripe.Customer = stripe.Customer.retrieve(id=user.stripeCustomerId)
        
        subscription: stripe.Subscription = stripe.Subscription.retrieve(checkout['subscription'])
        product: stripe.Product = stripe.Product.retrieve(subscription.plan.product)
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(stripeSubscriptionId=subscription.id)
            guild: DiscordGuild = await sync_to_async(DiscordGuild.objects.get)(id=config.guild)
        except:
            return redirect(reverse('events:pricing'))

        #print(subscription)
        #logger.event(f"Just Subscripbed to {product['name']}")

        return await sync_to_async(render)(request, 'app/success.html', context={
            "user" : request.user,
            "checkout" : checkout,
            "guild": guild,
            "cusid": user.stripeCustomerId.replace('cus_', ''),
            "product": product,
            "subscription": subscription,
            #"guilds" : guilds,
            })
        
        
class CancelView(TemplateView):
    template_name = 'app/canceled.html'

    @classonlymethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    @sync_to_async
    @method_decorator(login_required)
    @async_to_sync
    async def get(self, request: HttpRequest, *args, **kwargs):
        access_token = await sync_to_async(request.session.get)("access_token")
        if not access_token: #if token is valid
            return redirect("/login")

        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except UnauthorizedError:
                print("unauth")
                return redirect(AUTH_URL)

        await restapp.close()
        

        return await sync_to_async(render)(request, self.template_name, context={
            "user" : request.user,
            "cusid": user.stripeCustomerId.replace('cus_', ''),
            })


@csrf_exempt
async def create_checkout_session(request: HttpRequest):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        access_token = await sync_to_async(request.session.get)("access_token")
        
        IS_YEARLY = True if request.GET.get('yearly') == 'true' else False
        GUILD_ID = request.GET.get('guild_id')
        USER_ID = request.session.get("_auth_user_id")
        
        
        restapp = RESTApp()
        await restapp.start()

        async with restapp.acquire(access_token, "BEARER") as bearer:
            try:
                user: DUser = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
            except UnauthorizedError:
                print("unauth")
                return redirect(AUTH_URL)
        
        await restapp.close()
        
        
        try:
            config: Config = await sync_to_async(Config.objects.get)(guild=GUILD_ID)
        except Config.DoesNotExist:
            return JsonResponse({'error': 'Guild does not exist'})
        
        if config.is_premium:
            return JsonResponse({'error': 'Guild already has a subscription'})
        
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        #DOMAIN = "http://localhost"
        DOMAIN = "https://baast.app"
        
        price = settings.STRIPE_PRICE_ID[1] if IS_YEARLY else settings.STRIPE_PRICE_ID[0]

        session = stripe.checkout.Session.create(
            #payment_method_types=['card'],
            customer=user.stripeCustomerId,
            mode='subscription',
            line_items=[{
                'price': price,
                'quantity': 1,
            }],
            success_url=f"{DOMAIN}/subscription/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{DOMAIN}/pricing/",
            metadata={
                'guild_id': GUILD_ID,
                'user_id': USER_ID
            },
            automatic_tax={'enabled': True},
        )
        return JsonResponse({'url': session.url})


@csrf_exempt
def cancel_subscription(request: HttpRequest):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        GUILD_ID = request.GET.get('guild_id')
        USER_ID = request.session.get("_auth_user_id")
        
        try:
            config: Config = Config.objects.get(guild=GUILD_ID)
        except Config.DoesNotExist:
            return JsonResponse({'error': 'Guild does not exist'})
        
        try:
            user: User = User.objects.get(id=USER_ID)
        except:
            return JsonResponse({'error': 'User does not exist'})
        
        cus_subs = None
        try:
            cus_subs = stripe.Subscription.list(customer=user.stripeCustomerId)
            cus_subs = [sub.id for sub in cus_subs]
        except:
            cus_subs = None
        
        # subscription: stripe.Subscription = stripe.Subscription.retrieve(config.stripeSubscriptionId)
        
        if config.stripeSubscriptionId in cus_subs:
            try:
                session = stripe.billing_portal.Session.create(
                    customer = user.stripeCustomerId,
                    return_url = "https://baast.app/pricing/",
                    flow_data = {
                        "type": "subscription_cancel",
                        "subscription_cancel": {"subscription": config.stripeSubscriptionId},
                        "after_completion": {
                            "type": "redirect",
                            "redirect": {"return_url": "https://baast.app/subscription/canceled"},
                        },
                    },
                )
            except Exception as e:
                logger.error(f'Error cancelling subscription for user {USER_ID} in guild {GUILD_ID}\n {e}')
                
                return JsonResponse({'error': 'Error cancelling subscription, please contact support!'})
            
            return JsonResponse({'url': session.url})
        else:
            return JsonResponse({'error': 'Guild does not have a subscription'})


async def get_user_guilds(request: HttpRequest):
    user_id = request.session.get("_auth_user_id")
    access_token = request.session.get("access_token")
    
    guilds, user = None, None
    
    restapp = RESTApp()
    await restapp.start()
    
    async with restapp.acquire(access_token, "BEARER") as bearer:
        try:
            guilds = await convertGuilds(bearer.fetch_my_guilds(), user_id)
            user = await sync_to_async(DUser)(await bearer.fetch_my_user(), request.user)
        except UnauthorizedError or NotFoundError:
            print(f'{sys._getframe()}\n{sys.exc_info()}')
            await restapp.close()
            return redirect(reverse('discord:dash_home'))
        except:
            print(f'{sys._getframe()}\n{sys.exc_info()}')
        
    await restapp.close()
    
    return guilds, user



async def handler404(request, *args, **argv):
    #response = render_to_response('404.html', {}, context_instance=RequestContext(request))
    #response.status_code = 404
    # Match other public pages: header uses `user != 'none'`; AnonymousUser would wrongly show "logged in".
    return await sync_to_async(render)(request, '404.html', context={'user': 'none'}, status=404)

async def handler500(request, *args, **argv):
    # response = render_to_response('500.html', {}, context_instance=RequestContext(request))
    # response.status_code = 500
    return await sync_to_async(render)(request, '500.html', context={'user': 'none'}, status=500)

def blog_list(request):
    posts = Blog.objects.filter(is_published=True)
    
    # Filter by post type if specified
    post_type = request.GET.get('type')
    if post_type in ['news', 'changelog']:
        posts = posts.filter(post_type=post_type)
    
    paginator = Paginator(posts, 10)  # Show 10 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'app/blog.html', {'page_obj': page_obj})

def blog_detail(request, slug):
    post = get_object_or_404(Blog, slug=slug, is_published=True)
    # Get 3 most recent posts excluding the current post
    recent_posts = Blog.objects.filter(is_published=True).exclude(slug=slug).order_by('-created_at')[:3]
    return render(request, 'app/blog_detail.html', {'post': post, 'recent_posts': recent_posts})






class RobotsTxtView(TemplateView):
    template_name = "robots.txt"