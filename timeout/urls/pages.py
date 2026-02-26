from django.urls import path
from timeout.views import pages
from timeout.views import calendar as cal_views

urlpatterns = [
    path('', pages.landing, name='landing'),
    path('dashboard/', pages.dashboard, name='dashboard'),
    path('profile/', pages.profile, name='profile'),
    #path('calendar/', pages.calendar, name='calendar'),
    path('notes/', pages.notes, name='notes'),
    path('statistics/', pages.statistics, name='statistics'),
    path('social/', pages.social, name='social'),
    
    #path('calendar/', cal_views.calendar_view, name='calendar'),
    #path('calendar/add/', cal_views.event_create, name='event_create'),
]
