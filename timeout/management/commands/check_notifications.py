from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from timeout.services.notification_service import NotificationService

User = get_user_model()


class Command(BaseCommand):
    help = "Check upcoming deadlines and create notifications"

    def handle(self, *args, **kwargs):
        for user in User.objects.all():
            NotificationService.create_deadline_notifications(user)
            NotificationService.create_event_notifications(user)  # ADD THIS

        self.stdout.write(self.style.SUCCESS("Notifications checked."))