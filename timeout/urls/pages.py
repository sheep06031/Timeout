"""
URL patterns for the timeout app's main pages.
Includes:
- landing: Public landing page for unauthenticated users.
- dashboard: Main user dashboard with upcoming events, notes, deadlines, and social feed.
- profile: User profile page showing their info, posts, and current/upcoming events.
- profile/edit: Page to edit user profile information.
- settings: User settings page to update preferences and account info.
- statistics: Page showing insights into user's event patterns and focus sessions.
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
