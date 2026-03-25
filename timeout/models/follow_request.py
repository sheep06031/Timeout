from django.conf import settings
from django.db import models


class FollowRequest(models.Model):
    """Pending follow request from one user to another (private accounts)."""

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_follow_requests',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_follow_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Ensure one request per pair and order by most recent first."""
        unique_together = ('from_user', 'to_user')
        ordering = ['-created_at']

    def __str__(self):
        """Return a string representation showing who requested to follow whom."""
        return f'{self.from_user.username} → {self.to_user.username}'
