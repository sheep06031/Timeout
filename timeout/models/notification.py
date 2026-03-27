from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    Represents a user notification for various activities.

    Notifications can relate to events, posts, messages, or social interactions.
    Each notification tracks read/deleted status.
    """

    class Type(models.TextChoices):
        DEADLINE =      "deadline",      "Deadline"
        EVENT =         "event",         "Event"
        MESSAGE =       "message",       "Message"
        LIKE =          "like",          "Like"
        COMMENT =       "comment",       "Comment"
        BOOKMARK =      "bookmark",      "Bookmark"
        FOLLOW =        "follow",        "Follow"
        EXAM =          "exam",          "Exam"
        CLASS =         "class",         "Class"
        MEETING =       "meeting",       "Meeting"
        STUDY_SESSION = "study_session", "Study Session"

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
    conversation = models.ForeignKey(
        'Conversation',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    post = models.ForeignKey(
        'Post',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    deadline = models.ForeignKey(
        'Event',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    class Meta:
        """Order notifications by most recent first."""
        ordering = ['-created_at']

    def __str__(self):
        """Return a string representation with user and notification title."""
        return f"Notification for {self.user.username}: {self.title}"