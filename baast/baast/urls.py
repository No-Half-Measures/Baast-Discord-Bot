from django import views
from django.contrib import admin
from django.urls import include, path

from discord import views

urlpatterns = [
    path('', include('django_prometheus.urls')),
    #path('', views.null, name='index'),

    # LOGIN & AUTH PATHS
    path('login/', views.discord_login, name='Discord-Login'),
    path('login/redirect', views.discord_redirect, name='Discord-Redirect'),
    path('logout/', views.discord_logout, name='Discord-Logout'),

    path('', include('app.urls')),
    path('panel/', include('discord.urls')),
]
