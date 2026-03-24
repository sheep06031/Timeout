from django.conf import settings
from django.db import models
from timeout.models.notification import Notification
from django.dispatch import receiver


class Bookmark(models.Model):
    """Bookmark/save posts for later reference."""

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Order by newest first, ensure one bookmark per user-post pair, and index for user queries."""
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
    """Create a notification for the post author when someone bookmarks their post."""
    if created and instance.post.author != instance.user:
        Notification.objects.create(
            user=instance.post.author,
            title="🏷️ New Bookmark",
            message=f"{instance.user.username} bookmarked your post",
            type=Notification.Type.BOOKMARK,
            post=instance.post,
        )