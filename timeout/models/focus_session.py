"""
focus_session.py - Defines the FocusSession model representing a user's focus session.
"""


from django.db import models
from django.conf import settings


class FocusSession(models.Model):
    """
    Model representing a user's focus session.

    Each session records when the user started and ended their focus period,
    and the total duration of the session.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='focus_sessions',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()

    class Meta:
        """
        Metadata for the FocusSession model:
        - Orders sessions by most recent start time first
        """

        ordering = ['-started_at']

    def __str__(self):
        """
        Return a string representation showing the user,
        session duration, and start time.
        """

        return f"{self.user.username} – {self.duration_seconds}s @ {self.started_at:%Y-%m-%d %H:%M}"
