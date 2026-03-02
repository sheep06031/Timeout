from django.conf import settings
from django.db import models


class Event(models.Model):
    """Calendar event model."""

    class EventType(models.TextChoices):
        """Event type choices."""
        DEADLINE = 'deadline', 'Deadline'
        EXAM = 'exam', 'Exam'
        CLASS = 'class', 'Class'
        MEETING = 'meeting', 'Meeting'
        STUDY_SESSION = 'study_session', 'Study Session'
        OTHER = 'other', 'Other'

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_events'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=1000, blank=True)
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.OTHER
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    is_all_day = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_completed = models.BooleanField(default=False) # Added to track event

    class Meta:
        ordering = ['-start_datetime']
        indexes = [
            models.Index(
                fields=['creator', '-start_datetime'],
                name='timeout_eve_creator_idx'
            ),
            models.Index(
                fields=['start_datetime'],
                name='timeout_eve_start_idx'
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_datetime.date()})"
