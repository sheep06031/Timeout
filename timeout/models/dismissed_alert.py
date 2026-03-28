"""
dismissed_alert.py - Defines the DismissedAlert model for tracking user-dismissed alerts.
"""


from django.db import models
from django.conf import settings


class DismissedAlert(models.Model):
    """Model representing an alert that a user has dismissed. 
    This allows the system to remember which alerts a user has 
    chosen to hide, preventing them from being shown again in the future."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dismissed_alerts')
    alert_key = models.CharField(max_length=255)
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'alert_key')