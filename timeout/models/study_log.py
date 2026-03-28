"""
study_log.py - Defines the StudyLog model for tracking daily study activity, including pomodoros, notes created/edited, and focus minutes, with a method to calculate activity level for heatmap visualization.
"""


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
    notes_edited = models.PositiveSmallIntegerField(default=0)
    focus_minutes = models.PositiveSmallIntegerField(default=0)

    class Meta:
        """Ensure one log per user-date pair, order by most recent, and index for heatmap queries."""
        unique_together = ['user', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(
                fields=['user', '-date'],
                name='timeout_studylog_user_date_idx',
            ),
        ]

    def __str__(self):
        """Return a string representation with user and study date."""
        return f'{self.user.username} — {self.date}'

    @property
    def activity_level(self):
        """Return 0-4 intensity for heatmap cell."""
        score = self.pomodoros * 2 + self.notes_created + self.notes_edited + self.focus_minutes // 30
        if score == 0:
            return 0
        if score <= 2:
            return 1
        if score <= 5:
            return 2
        if score <= 10:
            return 3
        return 4
