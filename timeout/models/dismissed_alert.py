from django.db import models
from django.conf import settings


class DismissedAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dismissed_alerts')
    alert_key = models.CharField(max_length=255)
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'alert_key')