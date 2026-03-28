"""block.py - Defines the Block model representing a user blocking another user."""


from django.db import models
from django.conf import settings
from timeout.models.mixins import CreatedAtMixin


class Block(CreatedAtMixin, models.Model):
    """Model representing a user blocking another user."""
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocking',
        on_delete=models.CASCADE,
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='blocked_by',
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ('blocker', 'blocked')

    def __str__(self):
        """Return a string representation of the block relationship."""
        return f"{self.blocker} blocks {self.blocked}"