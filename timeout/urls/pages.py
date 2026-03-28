"""
URL patterns for the timeout app's main pages.
"""

from django.urls import path
from timeout.views import pages
from timeout.views import profile as profile_views
from timeout.views import settings as settings_views

urlpatterns = [
    path('banned/', pages.banned, name='banned'),
    path('', pages.landing, name='landing'),
    path('dashboard/', pages.dashboard, name='dashboard'),
    path('profile/', pages.profile, name='profile'),
    path('profile/edit/', profile_views.profile_edit, name='profile_edit'),
    path('profile/change-username/', profile_views.change_username, name='change_username'),
    path('settings/', settings_views.settings_view, name='settings'),
    path('settings/save/', settings_views.settings_save_ajax, name='settings_save'),
    path('statistics/', pages.statistics, name='statistics'),
    path('social/', pages.social, name='social'),
]
