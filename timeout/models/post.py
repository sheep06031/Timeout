"""
post.py - Defines the Post model representing a social media post with privacy controls, associated with calendar events, and including methods for likes, bookmarks, comments, and visibility checks.
"""


from django.conf import settings
from django.db import models
from timeout.models.mixins import TimestampMixin, OwnedMixin


class Post(TimestampMixin, OwnedMixin, models.Model):
    """Social media post with privacy controls."""

    class Privacy(models.TextChoices):
        """Class that determines the privacy of the post"""
        PUBLIC = 'public', 'Public'
        FOLLOWERS_ONLY = 'followers_only', 'Followers Only'

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts',
    )
    content = models.TextField(max_length=5000)
    event = models.ForeignKey(
        'Event',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
        help_text='Optional calendar event associated with this post'
    )
    privacy = models.CharField(
        max_length=20,
        choices=Privacy.choices,
        default=Privacy.PUBLIC,
    )

    class Meta:
        """Order posts by newest first and index for fast feed queries."""
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'author']),
        ]

    def __str__(self):
        """Return a string representation with author and first 50 chars of content."""
        preview = self.content[:50]
        return f'{self.author.username}: {preview}...'

    def get_like_count(self):
        """Return the number of likes on this post."""
        return self.likes.count()

    def is_liked_by(self, user):
        """Check if a user has liked this post."""
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def is_bookmarked_by(self, user):
        """Check if a user has bookmarked this post."""
        if not user.is_authenticated:
            return False
        return self.bookmarks.filter(user=user).exists()

    def get_comment_count(self):
        """Return the number of comments on this post."""
        return self.comments.count()

    def can_view(self, user):
        """Check if user can view this post based on privacy."""
        if self.privacy == self.Privacy.PUBLIC:
            return True
        if not user.is_authenticated:
            return False
        if self.author == user:
            return True
        return self.author.followers.filter(
            id=user.id
        ).exists()
