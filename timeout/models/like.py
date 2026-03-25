from django.conf import settings
from django.db import models
from timeout.models.notification import Notification
from django.dispatch import receiver



class Like(models.Model):
    """Like relationship between users and posts."""

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
        """Order by newest first, ensure one like per user-post pair, and index for post queries."""
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
    if created and instance.post.author != instance.user:
        Notification.objects.create(
            user=instance.post.author,
            title="❤️ New Like",
            message=f"{instance.user.username} liked your post",
            type=Notification.Type.LIKE,
            post=instance.post,
        )
