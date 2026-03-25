from django.db import models
from django.conf import settings


class FocusSession(models.Model):
    """Records a user's focus mode session with start time, end time, and duration."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='focus_sessions',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()

    class Meta:
        """Order focus sessions by most recent start time first."""
        ordering = ['-started_at']

    def __str__(self):
        """Return a string representation with username, duration, and start time."""
        return f"{self.user.username} – {self.duration_seconds}s @ {self.started_at:%Y-%m-%d %H:%M}"
