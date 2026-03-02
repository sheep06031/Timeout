from django.urls import path
from timeout.views import pages
from timeout.views import calendar as cal_views
from timeout.views import statistics as stat_views
from timeout.views import profile as profile_views



urlpatterns = [
    path('', pages.landing, name='landing'),
    path('dashboard/', pages.dashboard, name='dashboard'),
    path('profile/', pages.profile, name='profile'),
    path('profile/edit/', profile_views.profile_edit, name='profile_edit'),

    #path('calendar/', pages.calendar, name='calendar'),
    path('statistics/', pages.statistics, name='statistics'),
    path('social/', pages.social, name='social'),
    
    
    #path('calendar/', cal_views.calendar_view, name='calendar'),
    #path('calendar/add/', cal_views.event_create, name='event_create'),
]
