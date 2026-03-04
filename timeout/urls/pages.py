from django.urls import path
from timeout.views import pages
from timeout.views.event_details import event_details
from timeout.views.event_edit import event_edit
from timeout.views import calendar as cal_views
from timeout.views import statistics as stat_views
from timeout.views import profile as profile_views
from timeout.views import event_delete



urlpatterns = [
    path('', pages.landing, name='landing'),
    path('dashboard/', pages.dashboard, name='dashboard'),
    path('profile/', pages.profile, name='profile'),
    path('profile/edit/', profile_views.profile_edit, name='profile_edit'),

    #path('calendar/', pages.calendar, name='calendar'),
    path('statistics/', pages.statistics, name='statistics'),
    path('social/', pages.social, name='social'),
    path('event/<int:event_id>/', event_details, name='event_details'),
    path("event/<int:pk>/edit/", event_edit, name="event_edit"), 
    path('event/<int:pk>/delete/', event_delete.event_delete, name='event_delete'),
    
    
    #path('calendar/', cal_views.calendar_view, name='calendar'),
    #path('calendar/add/', cal_views.event_create, name='event_create'),
]
