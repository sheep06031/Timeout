from django.urls import path
from timeout.views import calendar as cal_views
from timeout.views import deadlines as deadline_views
from timeout.views.notifications import notifications_view, mark_notification_read
from timeout.views import ai_calendar as ai_cal_views
from timeout.views.notifications import poll_notifications
from timeout.views import event_cancel as event_cancel_views
from timeout.views import ai_reschedule as ai_reschedule_views

urlpatterns = [
    path('calendar/', cal_views.calendar_view, name='calendar'),
    path('calendar/add/', cal_views.event_create, name='event_create'),
    path('calendar/event/<int:pk>/subscribe/', cal_views.subscribe_event, name='subscribe_event'),
    path('calendar/ai-add/', ai_cal_views.ai_create_event, name='ai_event_create'),
    path('calendar/ai-reschedule/', ai_reschedule_views.ai_suggest_reschedule, name='ai_reschedule'),
    path('calendar/<int:pk>/cancel/', event_cancel_views.event_cancel, name='event_cancel'),
    path('deadlines/', deadline_views.deadline_list_view, name='deadline_list'),
    path('deadlines/<int:event_id>/complete/', deadline_views.deadline_mark_complete, name='deadline_mark_complete'),
    path("notifications/", notifications_view, name="notifications"),
    path("notifications/read/<int:notification_id>/", mark_notification_read, name="mark_notification_read"),
    path('notifications/poll/', poll_notifications, name='poll_notifications'),
]