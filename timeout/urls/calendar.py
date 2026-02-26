from django.urls import path
from timeout.views import calendar as cal_views

urlpatterns = [
    path('calendar/', cal_views.calendar_view, name='calendar'),
    path('calendar/add/', cal_views.event_create, name='event_create'),
]