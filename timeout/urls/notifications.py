from django.urls import path
from timeout.views.notifications import notifications_view, mark_notification_read, delete_notification, poll_notifications

"""Notifications URL patterns for the timeout app."""

urlpatterns = [
    path('', notifications_view, name='notifications'),
    path('read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'),
    path('poll/', poll_notifications, name='poll_notifications'),
    path('delete/<int:notification_id>/', delete_notification, name='delete_notification'),
]
