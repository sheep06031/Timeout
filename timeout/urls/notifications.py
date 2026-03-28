"""
URL patterns for the timeout app's notifications features.
Includes:
- notifications: Main notifications page showing all notifications for the user.
- mark_notification_read: Endpoint to mark a specific notification as read.
- mark_notification_unread: Endpoint to mark a specific notification as unread.
- mark_all_notifications_read: Endpoint to mark all notifications as read.
- mark_all_notifications_unread: Endpoint to mark all notifications as unread.
- delete_notification: Endpoint to dismiss a specific notification.
- delete_all_notifications: Endpoint to dismiss all notifications for the user.
- poll_notifications: Endpoint for AJAX polling to get new notifications since the last check.
"""
from django.urls import path 
from timeout.views.notifications import (
    notifications_view,
    mark_notification_read,
    delete_notification,
    poll_notifications,
    mark_notification_unread,
    mark_all_notifications_read,
    mark_all_notifications_unread,
    delete_all_notifications,
)
 
urlpatterns = [ 
    path('', notifications_view, name='notifications'), 
    path('read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'), 
    path('poll/', poll_notifications, name='poll_notifications'), 
    path('delete/<int:notification_id>/', delete_notification, name='delete_notification'), 
    path('read-all/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('unread/<int:notification_id>/', mark_notification_unread, name='mark_notification_unread'),
    path('unread-all/', mark_all_notifications_unread, name='mark_all_notifications_unread'),
    path('delete-all/', delete_all_notifications, name='delete_all_notifications'),
]