"""
bookmark.py - Defines the Bookmark model representing a user's bookmark of a post.
"""


from django.conf import settings
from django.db import models
from timeout.models.notification import Notification
from timeout.models.mixins import CreatedAtMixin, notify_post_action
from django.dispatch import receiver


class Bookmark(CreatedAtMixin, models.Model):
    """
    Model representing a bookmark of a post by a user. 
    
    The model ensures that a user can only bookmark a specific post once, 
    and provides an index for efficient querying of bookmarks by user. When a bookmark is created, 
    a notification is sent to the post author if the bookmarker is not the author themselves.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarks',
    )
    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='bookmarks',
    )

    class Meta:
        """
        Metadata for the Bookmark model:
        - Orders bookmarks so the most recent appear first
        - Ensures a user cannot bookmark the same post multiple times
        - Adds a database index to optimise queries filtering by user and recency
        """
        
        ordering = ['-created_at']
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        """Return a string representation showing which user bookmarked which post."""
        return f'{self.user.username} bookmarked {self.post.id}'
        
@receiver(models.signals.post_save, sender=Bookmark)
def create_bookmark_notification(sender, instance, created, **kwargs):
    """
    Automatically create a notification when a post is bookmarked

    Behaviour:
    - Only triggers when a new bookmark is created (not updated)
    - Does not notify if the user bookmarks their own post
    """

    if created:
        notify_post_action(instance, "🏷️", Notification.Type.BOOKMARK, "bookmarked")