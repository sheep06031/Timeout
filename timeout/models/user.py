import math

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model for the Timeout application."""

    class ManagementStyle(models.TextChoices):
        EARLY_BIRD = 'early_bird', 'Early Bird'
        NIGHT_OWL = 'night_owl', 'Night Owl'

    class Status(models.TextChoices):
        FOCUS    = 'focus',    '🎯 Focus Mode'
        SOCIAL   = 'social',   '💬 Social'
        INACTIVE = 'inactive', '😶 Inactive'

    status = models.CharField(  
        max_length=10,
        choices=Status.choices,
        default=Status.INACTIVE,
)
    # Profile fields
    middle_name = models.CharField(max_length=50, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    university = models.CharField(max_length=150, blank=True)
    year_of_study = models.PositiveIntegerField(null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
    )
    academic_interests = models.CharField(max_length=300, blank=True)

    # Focus timer
    focus_started_at = models.DateTimeField(null=True, blank=True)

    # Settings
    privacy_private = models.BooleanField(default=False)
    management_style = models.CharField(
        max_length=10,
        choices=ManagementStyle.choices,
        default=ManagementStyle.EARLY_BIRD,
    )

    # Appearance / Accessibility
    class Theme(models.TextChoices):
        LIGHT  = 'light',  'Light'
        DARK   = 'dark',   'Dark'
        SYSTEM = 'system', 'System Default'

    class ColorblindMode(models.TextChoices):
        NONE         = 'none',         'None'
        PROTANOPIA   = 'protanopia',   'Protanopia (Red-blind)'
        DEUTERANOPIA = 'deuteranopia', 'Deuteranopia (Green-blind)'
        TRITANOPIA   = 'tritanopia',   'Tritanopia (Blue-blind)'

    theme = models.CharField(
        max_length=10, choices=Theme.choices, default=Theme.LIGHT,
    )
    colorblind_mode = models.CharField(
        max_length=15, choices=ColorblindMode.choices, default=ColorblindMode.NONE,
    )
    font_size = models.PositiveSmallIntegerField(default=100)  # percentage, 80-150
    notification_sounds = models.BooleanField(default=True)
    pomo_work_minutes = models.PositiveSmallIntegerField(default=25)
    pomo_short_break = models.PositiveSmallIntegerField(default=5)
    pomo_long_break = models.PositiveSmallIntegerField(default=15)
    default_note_category = models.CharField(
        max_length=20, choices=[('', 'None')] + list(zip(
            ['lecture', 'todo', 'study_plan', 'personal', 'other'],
            ['Lecture', 'To-Do', 'Study Plan', 'Personal', 'Other'],
        )),
        default='', blank=True,
    )
    daily_study_reminder = models.TimeField(null=True, blank=True)

    # Daily Study Goals
    daily_pomo_goal = models.PositiveSmallIntegerField(default=4)
    daily_notes_goal = models.PositiveSmallIntegerField(default=3)
    daily_focus_goal = models.PositiveSmallIntegerField(default=120)  # minutes

    # Gamification
    xp = models.PositiveIntegerField(default=0)
    note_streak = models.PositiveIntegerField(default=0)
    longest_note_streak = models.PositiveIntegerField(default=0)
    last_note_date = models.DateField(null=True, blank=True)

    # Social
    following = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='followers',
        blank=True,
    )

    def __str__(self):
        return self.username

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(part for part in parts if part)

    @property
    def level(self):
        """Level = floor(sqrt(xp / 50)). Level 1 at 50 XP, 2 at 200, 3 at 450, etc."""
        return int(math.floor(math.sqrt(self.xp / 50))) if self.xp >= 50 else 0

    @property
    def xp_for_current_level(self):
        """XP threshold for current level."""
        return self.level ** 2 * 50

    @property
    def xp_for_next_level(self):
        """XP threshold for next level."""
        return (self.level + 1) ** 2 * 50

    @property
    def xp_progress_pct(self):
        """Percentage progress toward next level (0-100)."""
        current = self.xp_for_current_level
        nxt = self.xp_for_next_level
        if nxt == current:
            return 0
        return int(((self.xp - current) / (nxt - current)) * 100)

    @property
    def follower_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()
