from django.conf import settings
from django.db import models


class StudyLog(models.Model):
    """Tracks daily study activity for heatmap and goal tracking."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_logs',
    )
    date = models.DateField()
    pomodoros = models.PositiveSmallIntegerField(default=0)
    notes_created = models.PositiveSmallIntegerField(default=0)
    focus_minutes = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(
                fields=['user', '-date'],
                name='timeout_studylog_user_date_idx',
            ),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.date}'

    @property
    def activity_level(self):
        """Return 0-4 intensity for heatmap cell."""
        score = self.pomodoros * 2 + self.notes_created + self.focus_minutes // 30
        if score == 0:
            return 0
        if score <= 2:
            return 1
        if score <= 5:
            return 2
        if score <= 10:
            return 3
        return 4
