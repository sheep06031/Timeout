from django.conf import settings
from django.db import models
from django.utils import timezone


class Note(models.Model):
    """
    Model representing a personal note for a user.

    Notes can be linked to an Event and categorized for organization.
    Has pinned notes, deadlines, time tracking, and editor page modes.
    """

    class Category(models.TextChoices):
        """Available note category types for organizing user notes."""
        LECTURE = 'lecture', 'Lecture'
        TODO = 'todo', 'To-Do'
        STUDY_PLAN = 'study_plan', 'Study Plan'
        PERSONAL = 'personal', 'Personal'
        OTHER = 'other', 'Other'

    class PageMode(models.TextChoices):
        """Editor layout options: pageless (continuous) or paged (document-style)."""
        PAGELESS = 'pageless', 'Pageless'
        PAGED = 'paged', 'Paged'

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
    content = models.TextField()
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
    page_mode = models.CharField(
        max_length=10,
        choices=PageMode.choices,
        default=PageMode.PAGELESS,
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
        """
        Metadata for the Note model:
        - Orders pinned notes first, then by creation date
        - Indexes optimize queries by owner, pin status, and category
        """

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
        """Return a string representation with owner and first 50 chars of title."""
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
        """
        Determine urgency level based on proximity to due_date.

        Returns:
        - 'overdue': past due
        - 'urgent': due within 24 hours
        - 'soon': due within 3 days
        - 'upcoming': due later
        - None: no due_date
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
        """
        Format time_spent_minutes as human-readable string.

        Examples:
        - 0 minutes -> ''
        - 45 minutes -> '45m'
        - 120 minutes -> '2h'
        """

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
