from django.urls import path 
from timeout.views.notifications import (
    notifications_view,
    mark_notification_read,
    delete_notification,
    poll_notifications,
    mark_notification_unread,
    mark_all_notifications_read,
    mark_all_notifications_unread,
)
 
urlpatterns = [ 
    path('', notifications_view, name='notifications'), 
    path('read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'), 
    path('poll/', poll_notifications, name='poll_notifications'), 
    path('delete/<int:notification_id>/', delete_notification, name='delete_notification'), 
    path('read-all/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('unread/<int:notification_id>/', mark_notification_unread, name='mark_notification_unread'),
    path('unread-all/', mark_all_notifications_unread, name='mark_all_notifications_unread'),
]