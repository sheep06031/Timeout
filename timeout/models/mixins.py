"""
mixins.py - Defines reusable model mixins for common fields and permissions.
"""


from django.db import models


class TimestampMixin(models.Model):
    """Provides created_at and updated_at fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CreatedAtMixin(models.Model):
    """Provides a created_at field only (for models that don't track updates)."""
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class OwnedMixin(models.Model):
    """Provides can_edit/can_delete permission checks for models with an owner field."""

    class Meta:
        abstract = True

    def _get_owner(self):
        """Return the owner/author of this object."""
        return getattr(self, 'author', None) or getattr(self, 'owner', None)

    def can_edit(self, user):
        """Check if user can edit this object."""
        if not user.is_authenticated:
            return False
        return self._get_owner() == user

    def can_delete(self, user):
        """Check if user can delete this object."""
        if not user.is_authenticated:
            return False
        return self._get_owner() == user or user.is_staff


def notify_post_action(instance, emoji, notification_type, verb):
    """Create a notification when a user performs an action on a post (like, bookmark, etc.)."""
    from timeout.models.notification import Notification

    if instance.post.author != instance.user:
        Notification.objects.create(
            user=instance.post.author,
            title=f"{emoji} New {notification_type.label}",
            message=f"{instance.user.username} {verb} your post",
            type=notification_type,
            post=instance.post,
        )
