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
    def follower_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()
