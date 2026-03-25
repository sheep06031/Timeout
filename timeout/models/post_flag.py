from django.conf import settings
from django.db import models


class PostFlag(models.Model):
    """A flag/report on a post submitted by a user."""

    class Reason(models.TextChoices):
        """Reasons for flagging a post for moderation."""
        SPAM = 'spam', 'Spam'
        HARASSMENT = 'harassment', 'Harassment'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate Content'
        MISINFORMATION = 'misinformation', 'Misinformation'
        OTHER = 'other', 'Other'

    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='flags',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flagged_posts',
    )
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        default=Reason.OTHER,
    )
    description = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Ensure one flag per post-reporter pair and order by most recent first."""
        unique_together = ('post', 'reporter')
        ordering = ['-created_at']

    def __str__(self):
        """Return a string representation showing who flagged which post and why."""
        return f'{self.reporter.username} flagged post {self.post_id}: {self.reason}'
