from django.conf import settings
from django.db import models
from django.utils import timezone


class Note(models.Model):
    """Personal note with optional event link and category."""

    class Category(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        TODO = 'todo', 'To-Do'
        STUDY_PLAN = 'study_plan', 'Study Plan'
        PERSONAL = 'personal', 'Personal'
        OTHER = 'other', 'Other'

    CATEGORY_COLORS = {
        'lecture': 'primary',
        'todo': 'danger',
        'study_plan': 'success',
        'personal': 'info',
        'other': 'secondary',
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notes',
    )
    title = models.CharField(max_length=200)
    content = models.TextField(max_length=5000)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    event = models.ForeignKey(
        'Event',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notes',
        help_text='Optional calendar event linked to this note',
    )
    is_pinned = models.BooleanField(default=False)
    due_date = models.DateTimeField(
        null=True, blank=True,
        help_text='Optional deadline for this note',
    )
    time_spent_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Total Pomodoro minutes spent on this note',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(
                fields=['owner', '-is_pinned', '-created_at'],
                name='timeout_note_owner_pin_idx',
            ),
            models.Index(
                fields=['owner', 'category'],
                name='timeout_note_owner_cat_idx',
            ),
        ]

    def __str__(self):
        return f'{self.owner.username}: {self.title[:50]}'

    def get_color(self):
        """Return the Bootstrap color class for this category."""
        return self.CATEGORY_COLORS.get(self.category, 'secondary')

    def can_edit(self, user):
        """Check if user can edit this note."""
        if not user.is_authenticated:
            return False
        return self.owner == user

    @property
    def urgency(self):
        """Return urgency level based on due_date proximity.
        Returns: 'overdue', 'urgent', 'soon', 'upcoming', or None.
        """
        if not self.due_date:
            return None
        now = timezone.now()
        if self.due_date <= now:
            return 'overdue'
        delta = self.due_date - now
        hours = delta.total_seconds() / 3600
        if hours <= 24:
            return 'urgent'
        if hours <= 72:
            return 'soon'
        return 'upcoming'

    @property
    def time_spent_display(self):
        """Format time_spent_minutes as human-readable string."""
        if self.time_spent_minutes == 0:
            return ''
        hours = self.time_spent_minutes // 60
        mins = self.time_spent_minutes % 60
        if hours > 0:
            return f'{hours}h {mins}m' if mins else f'{hours}h'
        return f'{mins}m'

    def can_delete(self, user):
        """Check if user can delete this note."""
        if not user.is_authenticated:
            return False
        return self.owner == user or user.is_staff
