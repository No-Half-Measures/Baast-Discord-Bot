from django.urls import path, re_path

from . import views

app_name = 'events'
urlpatterns = [
    path('', views.IndexView, name='index'),
    path("robots.txt", views.RobotsTxtView.as_view(content_type="text/plain"), name="robots"),
    path('pricing', views.PricingView, name='pricing'),
    path('faq', views.FAQ, name='faq'),
    path('privacy_policy', views.Privacy, name='privacy'),
    path('terms_of_service', views.TOS, name='tos'),
    
    # User Stripe Portals
    path('manage-subscription', views.ManageSub, name='manage-subscription'),

    path('stripe/webhook/', views.stripe_webhook, name='webhook'),
    path('ajax/stripe/ccs', views.create_checkout_session, name="ccs"),
    path('ajax/stripe/cancel', views.cancel_subscription, name="cancel_sub"),
    path('subscription/success/', views.SuccessView.as_view(), name='sub_success'),
    path('subscription/canceled/', views.CancelView.as_view(), name='sub_cancel'),

    path('posts', views.blog_list, name='blog_list'),
    path('post/<slug:slug>', views.blog_detail, name='blog_detail'),
]

handler404 = views.handler404
handler500 = views.handler500