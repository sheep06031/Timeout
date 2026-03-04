from django.db import models
from django.conf import settings


class FocusSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='focus_sessions',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} – {self.duration_seconds}s @ {self.started_at:%Y-%m-%d %H:%M}"
