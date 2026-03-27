from django.conf import settings
from django.db import models
from timeout.models.notification import Notification
from django.dispatch import receiver



class Like(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)

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
    
    if created and instance.post.author != instance.user:
        Notification.objects.create(
            user=instance.post.author,
            title="❤️ New Like",
            message=f"{instance.user.username} liked your post",
            type=Notification.Type.LIKE,
            post=instance.post,
        )
