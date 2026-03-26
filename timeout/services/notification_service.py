from django.utils import timezone
from timeout.models.notification import Notification
from timeout.models.event import Event

class NotificationService:
    """Maps event type to friendly label for notification messages"""

    EVENT_TYPE_LABELS = {
        Event.EventType.DEADLINE:      ("Deadline",      "⏰"),
        Event.EventType.EXAM:          ("Exam",          "📝"),
        Event.EventType.CLASS:         ("Class",         "🏫"),
        Event.EventType.MEETING:       ("Meeting",       "🤝"),
        Event.EventType.STUDY_SESSION: ("Study Session", "📚"),
        Event.EventType.OTHER:         ("Event",         "📅"),
    }

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
            if 0 < time_to_end <= 3600:
                NotificationService._notify_once(user, event, "1 hour left to complete your deadline!")
            elif 3600 < time_to_end <= 86400:
                NotificationService._notify_once(user, event, "1 day left to complete your deadline!")
            elif 86400 < time_to_end <= 604800:
                NotificationService._notify_once(user, event, "1 week left to complete your deadline!")

    
    
    @staticmethod
    def create_event_notifications(user):
        """Check all upcoming event types and create notifications if needed."""
        now = timezone.now()
        event_types = [
            Event.EventType.EXAM, Event.EventType.CLASS,
            Event.EventType.MEETING, Event.EventType.STUDY_SESSION,
            Event.EventType.OTHER,
        ]
        upcoming_events = Event.objects.filter(
            creator=user, event_type__in=event_types,
            is_completed=False,
            status__in=[Event.EventStatus.UPCOMING, Event.EventStatus.ONGOING],
            start_datetime__gt=now,
        )
        for event in upcoming_events:
            NotificationService._notify_event_by_time(user, event, now)

    @staticmethod
    def _notify_event_by_time(user, event, now):
        """Send a time-based notification for an upcoming event."""
        label, icon = NotificationService.EVENT_TYPE_LABELS.get(
            event.event_type, ("Event", "📅")
        )
        time_to_start = (event.start_datetime - now).total_seconds()
        if 0 < time_to_start <= 3600:
            msg = f'Your {label} "{event.title}" starts in 1 hour!'
        elif 3600 < time_to_start <= 86400:
            msg = f'Your {label} "{event.title}" starts tomorrow!'
        elif 86400 < time_to_start <= 604800:
            msg = f'Your {label} "{event.title}" is coming up this week!'
        else:
            return
        NotificationService._notify_once(user, event, msg)

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
        """Create notification only if one does not already exist for this event and message."""
        exists = Notification.objects.filter(
            user=user,
            deadline=event,
            message=message
        ).exists()
        
        if not exists:
            label, icon = NotificationService.EVENT_TYPE_LABELS.get(
                event.event_type, ("Event", "📅")
            )
            Notification.objects.create(
                user=user,
                title=f"{icon} {label}: {event.title}",
                message=message,
                deadline=event,
                type=NotificationService._get_notification_type(event.event_type),
            )

    @staticmethod
    def _get_notification_type(event_type):
        """Map event type to notification type."""
        mapping = {
            Event.EventType.DEADLINE:      Notification.Type.DEADLINE,
            Event.EventType.EXAM:          Notification.Type.EXAM,
            Event.EventType.CLASS:         Notification.Type.CLASS,
            Event.EventType.MEETING:       Notification.Type.MEETING,
            Event.EventType.STUDY_SESSION: Notification.Type.STUDY_SESSION,
            Event.EventType.OTHER:         Notification.Type.EVENT,
        }
        return mapping.get(event_type, Notification.Type.EVENT)