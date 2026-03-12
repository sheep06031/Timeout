from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):

    class Type(models.TextChoices):
        DEADLINE = "deadline", "Deadline"
        EVENT = "event", "Event"
        MESSAGE = "message", "Message"
        LIKE = "like", "Like"
        COMMENT = "comment", "Comment"
        BOOKMARK = "bookmark", "Bookmark"
        FOLLOW = "follow", "Follow"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.DEADLINE
    )

    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    deadline = models.ForeignKey(
        'Event',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"