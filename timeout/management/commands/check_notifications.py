"""
check_notifications.py - Management command to check upcoming deadlines and events
                         and create notifications for all users accordingly.

This command iterates through all users in the system and uses the NotificationService
to create notifications for any upcoming deadlines and events that they have. It is 
intended to be run periodically (e.g., via a cron job) to ensure that users receive 
timely notifications about their deadlines and events.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from timeout.services.notification_service import NotificationService

User = get_user_model()

class Command(BaseCommand):
    """Management command to check upcoming deadlines and events, and create the notifications for all users accordingly."""
    help = "Check upcoming deadlines and create notifications"

    def handle(self, *args, **kwargs):
        """Iterate through all users and create notifications for deadlines and events."""
        for user in User.objects.all():
            NotificationService.create_deadline_notifications(user)
            NotificationService.create_event_notifications(user)  

        self.stdout.write(self.style.SUCCESS("Notifications checked."))