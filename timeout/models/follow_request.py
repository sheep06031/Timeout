"""
follow_request.py - Defines the FollowRequest model representing a pending follow request between users.
"""


from django.conf import settings
from django.db import models
from timeout.models.mixins import CreatedAtMixin


class FollowRequest(CreatedAtMixin, models.Model):
    """
    Model representing a pending follow request from one user to another.

    This ensures that a user can request to follow another user, and the 
    recipient can accept or delete the request. 
    """

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_follow_requests',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_follow_requests',
    )

    class Meta:
        """
        Metadata for the FollowRequest model:
        - Ensures that each user pair has at most one request
        - Orders requests so the most recent appear first
        """

        unique_together = ('from_user', 'to_user')
        ordering = ['-created_at']

    def __str__(self):
        """
        Return a string representation showing who requested to follow whom.
        """
        return f'{self.from_user.username} → {self.to_user.username}'
