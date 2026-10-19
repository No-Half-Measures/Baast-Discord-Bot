from django.urls import include, path

from . import views
from .pages.admin.blog import blog_list, blog_create, blog_edit, blog_delete, upload_image
from .pages import (EventsView, EventView, OverView, PanelView, ConfigView, StatsView, UserView, PresetsView, PresetView, TemplatesView, TemplateView,
                    AjaxEventDelete, AjaxTemplates, AjaxOptions, AjaxPreset, AjaxPresetDelete, AjaxLabel, AjaxLabelDelete, AjaxUpdateLabelOrder,
                    AjaxTemplate, AjaxTemplateDelete, AjaxPresetCells, AjaxTemplatePresetLink, AjaxPresetRoles, AjaxPresetRolesDelete, AjaxConfigUpdate, 
                    AjaxConfigReminderDelete, AjaxConfigReminderSave)
from .pages.admin import Announcer
from .metrics_view import DiscordMetricsView, DiscordHealthView, DiscordPoolStatusView

app_name = 'discord'
urlpatterns = [
    # Admin URLs
    path('admin/', include([
        path('guilds', views.dash_admin_guilds, name="admin_guilds"),
        path('announcer', Announcer.as_view(), name="admin_announcer"),
        path('post/', include([
            path('', blog_list, name='admin_blog_list'),
            path('create', blog_create, name='admin_blog_create'),
            path('<slug:slug>/edit', blog_edit, name='admin_blog_edit'),
            path('<slug:slug>/delete', blog_delete, name='admin_blog_delete'),
        ])),
        path('upload-image', upload_image, name='admin_upload_image'),
        path('upload_file_ajax', views.upload_file_ajax, name='admin_upload_file'),
    ])),
    
    # AJAX
    path('ajax/', include([
        path('guild/<str:hashguild>/', include([
            path('', views.admin_guild, name="a_guild"),
            path('config/<str:channel>/', views.config_update_event_chnls, name="ajax_config_channels"),
        ])),
        # event
        path('event/<str:hashguild>/', include([
            path('e/<str:eventid>/restore/', views.event_restore, name="event_restore"),
            path('e/<str:id>/del/', AjaxEventDelete.as_view(), name="event_del"),
            path('<str:eventid>/signup/del/<str:userid>/o/<str:signupoption>/', views.signup_delete, name="signup_del"),
        ])),
        # config
        path('config/<str:hashguild>/', include([
            path('c/<str:channel>', views.config_update_event_chnls, name="config_update_event_chnls"),
            path('save_reminder/', AjaxConfigReminderSave.as_view(), name='config_save_reminder'),
            path('delete_reminder/', AjaxConfigReminderDelete.as_view(), name='config_delete_reminder'),
            path('update_settings/', AjaxConfigUpdate.as_view(), name='config_update_settings'),
        ])),
        # template
        path('template/<str:hashguild>/', include([
            path('get/', AjaxTemplates.as_view(), name="get_templates"),
            path('options/get/<str:template>/', AjaxOptions.as_view(), name="get_options"),
            path('<str:id>/', AjaxTemplate.as_view(), name="ajax_template"),
            path('<str:id>/del/', AjaxTemplateDelete.as_view(), name="dash_template_del"),
            path('<str:id>/<str:pid>/', AjaxPresetCells.as_view(), name="ajax_template_cells"),
            path('<str:id>/link/<str:action>/', AjaxTemplatePresetLink.as_view(), name="ajax_template_link"),
        ])),
        # preset
        path('preset/<str:hashguild>/', include([
            path('', AjaxPreset.as_view(), name="dash_preset_new"),
            path('roles/save/<str:preset>/<str:roleset>/', AjaxPresetRoles.as_view(), name="save_preset_roles"),
            path('roles/get/<str:preset>/', AjaxPresetRoles.as_view(), name="get_rolesets"),
            path('roles/get/<str:preset>/<str:roleset>/', AjaxPresetRoles.as_view(), name="get_preset_role"),
            path('roles/delete/<str:preset>/<str:roleset>/', AjaxPresetRolesDelete.as_view(), name="delete_preset_role"),
            path('<str:id>/', AjaxPreset.as_view(), name="dash_preset_save"),
            path('<str:id>/del/', AjaxPresetDelete.as_view(), name="dash_preset_del"),
        ])),
        # option
        path('option/<str:hashguild>/', include([
            path('<str:id>/save/', AjaxLabel.as_view(), name="dash_option_save"),
            path('<str:id>/del/', AjaxLabelDelete.as_view(), name="dash_option_del"),
            path('<str:id>/updateorder/', AjaxUpdateLabelOrder.as_view(), name="dash_update_options_order"),
        ])),
        # Other
        path('options/get/<str:option>/<str:hashguild>/', AjaxOptions.as_view(), name="get_option_by_id"),
    ])),
    
    # Main application URLs
    path('', PanelView.as_view(), name='dash_home'),
    path('user', UserView.as_view(), name="dash_user"),
    path('<str:hashguild>', include([
        path('', OverView.as_view(), name="dash_overview"),
        path('/config', ConfigView.as_view(), name="dash_config"),
        path('/events', EventsView.as_view(), name='dash_events'),
        path('/event/<str:id>', EventView.as_view(), name='dash_event'),
        path('/event/<str:id>/linked', EventView.as_view(), name='dash_event_linked'),
        path('/stats', StatsView.as_view(), name="dash_stats"),
        path('/presets', PresetsView.as_view(), name="dash_presets"),
        path('/preset/<str:id>', PresetView.as_view(), name="dash_preset"),
        path('/templates', TemplatesView.as_view(), name="dash_templates"),
        path('/template/<str:id>', TemplateView.as_view(), name="dash_template"),
    ])),
    
    # Monitoring and Metrics (TO-DO: Move out of Panel)
    path('metrics/', DiscordMetricsView.as_view(), name="discord_metrics"),
    path('health/', DiscordHealthView.as_view(), name="discord_health"),
    path('pool-status/', DiscordPoolStatusView.as_view(), name="discord_pool_status"),
]
