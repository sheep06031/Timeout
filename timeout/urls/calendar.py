from django.urls import path
from timeout.views import calendar as cal_views
from timeout.views import deadlines as deadline_views

urlpatterns = [
    path('calendar/', cal_views.calendar_view, name='calendar'),
    path('calendar/add/', cal_views.event_create, name='event_create'),
    path('deadlines/', deadline_views.deadline_list_view, name='deadline_list'),
    path(
        'deadlines/<int:event_id>/complete/',
        deadline_views.deadline_mark_complete,
        name='deadline_mark_complete',
    ),
]