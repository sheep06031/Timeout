from django.conf import settings
from django.db import models



class Conversation(models.Model):
    """
    Model representing a conversation thread between two users.

    Each conversation has multiple participants and tracks timestamps for
    creation and last update. The most recently updated conversations are ordered first.
    """

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadata for the Conversation model:
        - Orders conversations by most recently updated first
        """

        ordering = ['-updated_at']

    def __str__(self):
        """Return a string representation with the conversation ID."""
        return f'Conversation {self.id}'

    def get_other_participant(self, user):
        """Return the other user in the conversation."""
        return self.participants.exclude(id=user.id).first()

    def get_last_message(self):
        """Return the most recent message."""
        return self.messages.order_by('-created_at', '-pk').first()


class Message(models.Model):
    """
    Model representing a single message within a conversation.

    Each message is associated with a conversation and a sender, and
    tracks when it was created and whether it has been read.
    """

    # The conversation this message belongs to
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    # The user who sent the message
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )

    # The content of the message, with a 2000 character limit
    content = models.TextField(max_length=2000)

    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        """
        Metadata for the Message model:
        - Orders messages by creation time (oldest first)
        """

        ordering = ['created_at']

    def __str__(self):
        """Return a string representation with sender and first 30 chars of content."""
        return f'{self.sender.username}: {self.content[:30]}'