"""
Messaging related URL patterns for the timeout app.
Includes:
- inbox: View to display the user's inbox with all conversations.
- conversation: View to display a specific conversation.
- start_conversation: View to start a new conversation with a specific user.
- send_message: Endpoint to send a message in a specific conversation.
- poll_messages: Endpoint for AJAX polling to get new messages in a conversation.
- delete_message: Endpoint to delete a specific message.
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