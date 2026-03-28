"""Calendar and event management related URL patterns for the timeout app.
Includes:
- calendar: Main calendar view showing user's events and deadlines.
- calendar/add: View to create a new event.
- calendar/event/<int:pk>/subscribe: Endpoint to subscribe to an event.
- calendar/ai-add: View to create a new event with AI assistance.
- calendar/ai-reschedule: View to get AI suggestions for rescheduling events.
- calendar/reschedule-study-sessions: Endpoint to apply AI-suggested study session rescheduling.
- calendar/apply-session-schedule: Endpoint to apply a generated session schedule to the calendar.
- calendar/dismiss-alert: Endpoint to dismiss a calendar alert notification.
- deadlines: View to list upcoming deadlines.
- deadlines/<int:event_id>/complete: Endpoint to mark a deadline as complete.
- event/<int:event_id>/: View to see details of a specific event.
- event/<int:pk>/edit/: View to edit a specific event.
- event/<int:pk>/delete/: View to delete a specific event.
- notifications/: Main notifications page showing all notifications for the user.
- notifications/read/<int:notification_id>/: Endpoint to mark a specific notification as read.
- notifications/poll/: Endpoint for AJAX polling to get new notifications since the last check.
- notifications/delete/<int:notification_id>/: Endpoint to dismiss a specific notification.
"""
from django.urls import path
from timeout.views import calendar as cal_views
from timeout.views import deadlines as deadline_views
from timeout.views import ai_calendar as ai_cal_views
from timeout.views import ai_reschedule as ai_reschedule_views
from timeout.views import event_edit as edit_views
from timeout.views import event_details as detail_views
from timeout.views import event_delete as delete_views
from timeout.views.notifications import delete_notification, mark_notification_read, notifications_view, poll_notifications

urlpatterns = [
    path('calendar/', cal_views.calendar_view, name='calendar'),
    path('calendar/add/', cal_views.event_create, name='event_create'),
    path('calendar/event/<int:pk>/subscribe/', cal_views.subscribe_event, name='subscribe_event'),
    path('calendar/ai-add/', ai_cal_views.ai_create_event, name='ai_event_create'),
    path('calendar/ai-reschedule/', ai_reschedule_views.ai_suggest_reschedule, name='ai_reschedule'),
    path('calendar/reschedule-study-sessions/', ai_reschedule_views.reschedule_study_sessions, name='reschedule_study_sessions'),
    path('calendar/apply-session-schedule/', cal_views.apply_session_schedule, name='apply_session_schedule'),
    path('calendar/dismiss-alert/', cal_views.dismiss_alert, name='dismiss_alert'),
    path('deadlines/', deadline_views.deadline_list_view, name='deadline_list'),
    path('deadlines/<int:event_id>/complete/', deadline_views.deadline_mark_complete, name='deadline_mark_complete'),
    
    # Event CRUD, click an event to view/edit/delete
    path('event/<int:event_id>/', detail_views.event_details, name='event_details'),
    path('event/<int:pk>/edit/', edit_views.event_edit, name='event_edit'),
    path('event/<int:pk>/delete/', delete_views.event_delete, name='event_delete'),
    path('deadlines/<int:event_id>/complete/', deadline_views.deadline_mark_complete, name='deadline_mark_complete'),
    path('deadlines/<int:event_id>/incomplete/', deadline_views.deadline_mark_incomplete, name='deadline_mark_incomplete'),
    path("notifications/", notifications_view, name="notifications"),
    path("notifications/read/<int:notification_id>/", mark_notification_read, name="mark_notification_read"),
    path('notifications/poll/', poll_notifications, name='poll_notifications'),
    path("notifications/delete/<int:notification_id>/", delete_notification, name="delete_notification"),
]