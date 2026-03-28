"""
Messaging related URL patterns for the timeout app.
"""

from django.urls import path
from timeout.views import messaging

urlpatterns = [
    path('inbox/', messaging.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', messaging.conversation, name='conversation'),
    path('conversation/start/<str:username>/', messaging.start_conversation, name='start_conversation'),
    path('conversation/<int:conversation_id>/send/', messaging.send_message, name='send_message'),
    path('conversation/<int:conversation_id>/poll/', messaging.poll_messages, name='poll_messages'),
    path('message/<int:message_id>/delete/', messaging.delete_message, name='delete_message'),
]