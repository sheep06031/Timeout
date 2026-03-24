from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Event(models.Model):
    """Calendar event model."""

    class Visibility(models.TextChoices):
        """Event visibility choices."""
        PUBLIC = 'public', 'Public'
        PRIVATE = 'private', 'Private'

    class EventType(models.TextChoices):
        """Event type choices."""
        DEADLINE = 'deadline', 'Deadline'
        EXAM = 'exam', 'Exam'
        CLASS = 'class', 'Class'
        MEETING = 'meeting', 'Meeting'
        STUDY_SESSION = 'study_session', 'Study Session'
        OTHER = 'other', 'Other'

    class EventStatus(models.TextChoices):
        """Event status choices."""
        UPCOMING = 'upcoming', 'Upcoming'
        ONGOING = 'ongoing', 'Ongoing'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    class EventPriority(models.TextChoices):
        """Event priority choices."""
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class EventRecurrence(models.TextChoices):
        """Event recurrence choices."""
        NONE = 'none', 'None'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'


    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_events',  # ← now you can use user.created_events
        null=True,
        blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=1000, blank=True)
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.OTHER
    )

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.UPCOMING
    )

    recurrence = models.CharField(
        max_length=10,
        choices=EventRecurrence.choices,
        blank=True,
        default=EventRecurrence.NONE,
    )

    allow_conflict = models.BooleanField(
        default=False,
        help_text='if true, event overlaps with others'
    )

    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE
    )

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    is_all_day = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_global = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False) # Added to track event

    linked_study_sessions = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="linked_deadlines",
        limit_choices_to={"event_type": "study_session"},
    )
    

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

    def clean(self):
        """
        Prevent overlapping events for the same user unless allowed.
        """

        # 1️⃣ Basic time validation
        if self.start_datetime >= self.end_datetime:
            raise ValidationError("End time must be after start time.")

        # 2️⃣ Define which types cannot overlap
        non_overlapping_types = [
            self.EventType.CLASS,
            self.EventType.STUDY_SESSION,
            self.EventType.EXAM,
            self.EventType.MEETING,
        ]

        # 3️⃣ Only check conflicts if the event type is in non_overlapping_types
        if self.event_type not in non_overlapping_types:
            return  # deadlines & "other" can overlap freely

        # 4️⃣ Ignore cancelled events
        if self.status == self.EventStatus.CANCELLED:
            return

        # 5️⃣ Check for overlapping events for this user
        overlapping_events = Event.objects.filter(
            creator=self.creator,
            start_datetime__lt=self.end_datetime,
            end_datetime__gt=self.start_datetime,
        ).exclude(pk=self.pk).filter(event_type__in=non_overlapping_types)

        if overlapping_events.exists():
            conflict = overlapping_events.first()
            raise ValidationError(
                f'This event conflicts with "{conflict.title}" '
                f'({conflict.start_datetime:%d %b %H:%M} - '
                f'{conflict.end_datetime:%H:%M}).'
            )
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        from .post import Post  # adjust if needed

        # If event is PUBLIC → ensure post exists
        if self.visibility == self.Visibility.PUBLIC and self.creator:

            existing_post = self.posts.first()

            post_content = (
                f"📅 {self.title}\n\n"
                f"{self.description}\n\n"
                f"🕒 {self.start_datetime:%d %b %Y %H:%M}"
            )

            if existing_post:
                # Update existing post
                existing_post.content = post_content
                existing_post.save()
            else:
                # Create new post
                Post.objects.create(
                    author=self.creator,
                    content=post_content,
                    event=self,
                    privacy=Post.Privacy.PUBLIC,
                )

        # If event is PRIVATE → delete any linked post
        else:
            self.posts.all().delete()

    def delete(self, *args, **kwargs):
        self.posts.all().delete()
        super().delete(*args, **kwargs)

    @property
    def is_past(self):
        """Check if the event has already occurred."""
        from django.utils import timezone
        return self.end_datetime < timezone.now()

    @property
    def is_ongoing(self):
        """Check if the event is currently happening."""
        from django.utils import timezone
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime

    @property
    def is_upcoming(self):
        """Check if the event is in the future."""
        from django.utils import timezone
        return self.start_datetime > timezone.now()
    
    def mark_completed(self):
        """Mark event as completed."""
        self.is_completed = True
        self.save(update_fields=['is_completed', 'updated_at'])

    def __str__(self):
        return f"{self.title} ({self.start_datetime.date()})"
