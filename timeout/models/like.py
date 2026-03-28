"""
like.py - Defines the Like model representing a user's like of a post, including automatic notification creation.
"""


from django.conf import settings
from django.db import models
from timeout.models.notification import Notification
from timeout.models.mixins import CreatedAtMixin, notify_post_action
from django.dispatch import receiver



class Like(CreatedAtMixin, models.Model):
    """
    Model representing a like relationship between a user and a post.

    A user can only like a specific post once. When a like is created,
    a notification is sent to the post author if the liker is not the author themselves.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes',
    )
    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='likes',
    )

    class Meta:
        """
        Metadata for the Like model:
        - Orders likes so the most recent appear first
        - Ensures a user cannot like the same post multiple times
        - Adds a database index to optimize queries filtering by post and recency
        """
        
        ordering = ['-created_at']
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        """Return a string representation showing which user liked which post."""
        return f'{self.user.username} likes {self.post.id}'

@receiver(models.signals.post_save, sender=Like)
def create_like_notification(sender, instance, created, **kwargs):
    """
    Automatically create a notification when a post is liked.

    Behaviour:
    - Only triggers when a new like is created (not updated)
    - Does not notify if the user likes their own post
    """
    
    if created:
        notify_post_action(instance, "❤️", Notification.Type.LIKE, "liked")
