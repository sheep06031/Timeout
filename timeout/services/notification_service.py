from django.utils import timezone
from timeout.models.notification import Notification
from timeout.models.event import Event

class NotificationService:

    @staticmethod
    def create_deadline_notifications(user):
        """Check upcoming deadlines and create notifications if needed."""
        now = timezone.now()
        upcoming_deadlines = Event.objects.filter(
            creator=user,
            event_type=Event.EventType.DEADLINE,
            is_completed=False,
        )

        for event in upcoming_deadlines:
            time_to_end = (event.end_datetime - now).total_seconds()

            # Send notifications for 1 hour, 1 day, 1 week remaining
            if 0 < time_to_end <= 3600:  # 1 hour
                NotificationService._notify_once(user, event, "1 hour left to complete your deadline!")
            elif 3600 < time_to_end <= 86400:  # 1 day
                NotificationService._notify_once(user, event, "1 day left to complete your deadline!")
            elif 86400 < time_to_end <= 604800:  # 1 week
                NotificationService._notify_once(user, event, "1 week left to complete your deadline!")

    @staticmethod
    def create_event_notifications(user):
        """Check upcoming events and create notifications if needed."""
        now = timezone.now()
        upcoming_events = Event.objects.filter(
            creator=user,
            event_type=Event.EventType.EVENT,
            is_completed=False,
            start_datetime__gt=now
        )

        for event in upcoming_events:
            time_to_start = (event.start_datetime - now).total_seconds()

            # Send notifications for 1 hour, 1 day, 1 week remaining
            if 0 < time_to_start <= 3600:  # 1 hour
                NotificationService._notify_once(user, event, "Your event starts in 1 hour!")
            elif 3600 < time_to_start <= 86400:  # 1 day
                NotificationService._notify_once(user, event, "Your event starts in 1 day!")
            elif 86400 < time_to_start <= 604800:  # 1 week
                NotificationService._notify_once(user, event, "Your event starts in 1 week!")

    @staticmethod
    def create_message_notification(user, message):
        """Create a notification for a new message."""

        conversation = message.conversation
        sender = message.sender

        recipient = conversation.participants.exclude(id=sender.id).first()

        if not recipient:
            return


        Notification.objects.create(
            user=user,
            title="New Message",
            message=message,
            type=Notification.Type.MESSAGE
        )

    @staticmethod
    def _notify_once(user, event, message):
        """Create notification if one does not exist for this deadline and message."""
        exists = Notification.objects.filter(user=user, deadline=event, message=message).exists()
        if not exists:
            Notification.objects.create(
                user=user,
                title=f"Deadline: {event.title}",
                message=message,
                deadline=event
            )