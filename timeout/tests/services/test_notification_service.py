from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.notification import Notification
from timeout.models.event import Event
from timeout.services.notification_service import NotificationService

User = get_user_model()


def make_event(creator, event_type, title='Test Event', delta_start=None, delta_end=None, status=None):
    """Helper to create an event with timezone-aware datetimes."""
    now = timezone.now()
    start = now + (delta_start or timezone.timedelta(days=1))
    end = now + (delta_end or timezone.timedelta(days=1, hours=1))
    kwargs = dict(
        creator=creator,
        title=title,
        event_type=event_type,
        start_datetime=start,
        end_datetime=end,
        is_completed=False,
    )
    if status:
        kwargs['status'] = status
    return Event.objects.create(**kwargs)


class GetNotificationTypeTests(TestCase):
    """Tests for _get_notification_type mapping."""

    def test_deadline_maps_to_deadline(self):
        """Test that DEADLINE event type maps to DEADLINE notification type."""
        result = NotificationService._get_notification_type(Event.EventType.DEADLINE)
        self.assertEqual(result, Notification.Type.DEADLINE)

    def test_exam_maps_to_exam(self):
        """Test that EXAM event type maps to EXAM notification type."""
        result = NotificationService._get_notification_type(Event.EventType.EXAM)
        self.assertEqual(result, Notification.Type.EXAM)

    def test_class_maps_to_class(self):
        """Test that CLASS event type maps to CLASS notification type."""
        result = NotificationService._get_notification_type(Event.EventType.CLASS)
        self.assertEqual(result, Notification.Type.CLASS)

    def test_meeting_maps_to_meeting(self):
        """Test that MEETING event type maps to MEETING notification type."""
        result = NotificationService._get_notification_type(Event.EventType.MEETING)
        self.assertEqual(result, Notification.Type.MEETING)

    def test_study_session_maps_to_study_session(self):
        """Test that STUDY_SESSION event type maps to STUDY_SESSION notification type."""
        result = NotificationService._get_notification_type(Event.EventType.STUDY_SESSION)
        self.assertEqual(result, Notification.Type.STUDY_SESSION)

    def test_other_maps_to_event(self):
        """Test that OTHER event type maps to EVENT notification type."""
        result = NotificationService._get_notification_type(Event.EventType.OTHER)
        self.assertEqual(result, Notification.Type.EVENT)

    def test_unknown_type_falls_back_to_event(self):
        """Test that unknown event types fall back to EVENT notification type."""
        result = NotificationService._get_notification_type('unknown_type')
        self.assertEqual(result, Notification.Type.EVENT)


class NotifyOnceTests(TestCase):
    """Tests for _notify_once deduplication logic."""

    def setUp(self):
        """Set up test data for NotifyOnceTests."""
        self.user = User.objects.create_user(username='user', password='pass')
        self.event = make_event(self.user, Event.EventType.DEADLINE, title='Assignment 1')

    def test_creates_notification_first_time(self):
        """Test that _notify_once creates a notification the first time."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_does_not_duplicate_same_message(self):
        """Test that _notify_once does not create duplicate notifications for the same message."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_creates_separate_for_different_messages(self):
        """Test that _notify_once creates separate notifications for different messages."""
        NotificationService._notify_once(self.user, self.event, '1 week left!')
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    def test_notification_title_includes_icon_and_label(self):
        """Test that the notification title includes the correct icon and label."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        n = Notification.objects.get(user=self.user)
        self.assertIn('⏰', n.title)
        self.assertIn('Deadline', n.title)
        self.assertIn(self.event.title, n.title)

    def test_notification_has_correct_type_for_deadline(self):
        """Test that the notification has the correct type for DEADLINE events."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        n = Notification.objects.get(user=self.user)
        self.assertEqual(n.type, Notification.Type.DEADLINE)

    def test_notification_has_correct_type_for_exam(self):
        """Test that the notification has the correct type for EXAM events."""
        exam = make_event(self.user, Event.EventType.EXAM, title='Final Exam')
        NotificationService._notify_once(self.user, exam, 'starts tomorrow!')
        n = Notification.objects.get(user=self.user, deadline=exam)
        self.assertEqual(n.type, Notification.Type.EXAM)

    def test_notification_linked_to_event(self):
        """Test that the notification is linked to the correct event."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        n = Notification.objects.get(user=self.user)
        self.assertEqual(n.deadline, self.event)

    def test_notification_is_unread_by_default(self):
        """Test that the notification is unread by default."""
        NotificationService._notify_once(self.user, self.event, '1 day left!')
        n = Notification.objects.get(user=self.user)
        self.assertFalse(n.is_read)


class CreateDeadlineNotificationsTests(TestCase):
    """Tests for create_deadline_notifications."""

    def setUp(self):
        """Set up test data for CreateDeadlineNotificationsTests."""
        self.user = User.objects.create_user(username='user', password='pass')

    def test_creates_notification_within_one_hour(self):
        """Test that create_deadline_notifications creates a notification for deadlines within one hour."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Urgent',
            delta_start=timezone.timedelta(minutes=-30),
            delta_end=timezone.timedelta(minutes=30),
        )
        NotificationService.create_deadline_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='1 hour'
        ).exists())

    def test_creates_notification_within_one_day(self):
        """Test that create_deadline_notifications creates a notification for deadlines within one day."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Due Soon',
            delta_start=timezone.timedelta(hours=-1),
            delta_end=timezone.timedelta(hours=12),
        )
        NotificationService.create_deadline_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='1 day'
        ).exists())

    def test_creates_notification_within_one_week(self):
        """Test that create_deadline_notifications creates a notification for deadlines within one week."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Coming Up',
            delta_start=timezone.timedelta(days=-1),
            delta_end=timezone.timedelta(days=3),
        )
        NotificationService.create_deadline_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='1 week'
        ).exists())

    def test_no_notification_for_far_future_deadline(self):
        """Test that create_deadline_notifications does not create a notification for deadlines far in the future."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Far Away',
            delta_start=timezone.timedelta(days=10),
            delta_end=timezone.timedelta(days=30),
        )
        NotificationService.create_deadline_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_no_notification_for_completed_deadline(self):
        """Test that create_deadline_notifications does not create a notification for completed deadlines."""
        event = make_event(
            self.user, Event.EventType.DEADLINE, title='Done',
            delta_start=timezone.timedelta(hours=-1),
            delta_end=timezone.timedelta(hours=12),
        )
        event.is_completed = True
        event.save()
        NotificationService.create_deadline_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_no_duplicate_notifications(self):
        """Test that create_deadline_notifications does not create duplicate notifications."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Due Soon',
            delta_start=timezone.timedelta(hours=-1),
            delta_end=timezone.timedelta(hours=12),
        )
        NotificationService.create_deadline_notifications(self.user)
        NotificationService.create_deadline_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_no_notification_for_other_users_deadlines(self):
        """Test that create_deadline_notifications does not create notifications for other users' deadlines."""
        other = User.objects.create_user(username='other', password='pass')
        make_event(
            other, Event.EventType.DEADLINE, title='Other Due',
            delta_start=timezone.timedelta(hours=-1),
            delta_end=timezone.timedelta(hours=12),
        )
        NotificationService.create_deadline_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)


class CreateEventNotificationsTests(TestCase):
    """Tests for create_event_notifications."""

    def setUp(self):
        """Set up test data for CreateEventNotificationsTests."""
        self.user = User.objects.create_user(username='user', password='pass')

    def test_creates_notification_for_exam_starting_in_one_hour(self):
        """Test that create_event_notifications creates a notification for exams starting in one hour."""
        make_event(
            self.user, Event.EventType.EXAM, title='Finals',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='1 hour'
        ).exists())

    def test_creates_notification_for_class_starting_tomorrow(self):
        """Test that create_event_notifications creates a notification for classes starting tomorrow."""
        make_event(
            self.user, Event.EventType.CLASS, title='Lecture',
            delta_start=timezone.timedelta(hours=20),
            delta_end=timezone.timedelta(hours=21),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='tomorrow'
        ).exists())

    def test_creates_notification_for_meeting_this_week(self):
        """Test that create_event_notifications creates a notification for meetings happening this week."""
        make_event(
            self.user, Event.EventType.MEETING, title='Supervisor',
            delta_start=timezone.timedelta(days=3),
            delta_end=timezone.timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='this week'
        ).exists())

    def test_notification_type_matches_event_type_exam(self):
        """Test that create_event_notifications sets the correct notification type for exams."""
        make_event(
            self.user, Event.EventType.EXAM, title='Midterm',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        n = Notification.objects.filter(user=self.user).first()
        self.assertEqual(n.type, Notification.Type.EXAM)

    def test_notification_type_matches_event_type_meeting(self):
        """Test that create_event_notifications sets the correct notification type for meetings."""
        make_event(
            self.user, Event.EventType.MEETING, title='Standup',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        n = Notification.objects.filter(user=self.user).first()
        self.assertEqual(n.type, Notification.Type.MEETING)

    def test_notification_type_matches_event_type_study_session(self):
        """Test that create_event_notifications sets the correct notification type for study sessions."""
        make_event(
            self.user, Event.EventType.STUDY_SESSION, title='Revision',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        n = Notification.objects.filter(user=self.user).first()
        self.assertEqual(n.type, Notification.Type.STUDY_SESSION)

    def test_does_not_create_notification_for_deadline_type(self):
        """Deadlines are handled by create_deadline_notifications, not this method."""
        make_event(
            self.user, Event.EventType.DEADLINE, title='Assignment',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(hours=12),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_does_not_create_notification_for_completed_event(self):
        """Test that create_event_notifications does not create a notification for completed events."""
        event = make_event(
            self.user, Event.EventType.EXAM, title='Old Exam',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        event.is_completed = True
        event.save()
        NotificationService.create_event_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_no_notification_for_far_future_event(self):
        """Test that create_event_notifications does not create a notification for events far in the future."""
        make_event(
            self.user, Event.EventType.EXAM, title='Far Exam',
            delta_start=timezone.timedelta(days=14),
            delta_end=timezone.timedelta(days=14, hours=2),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_no_duplicate_event_notifications(self):
        """Test that create_event_notifications does not create duplicate notifications."""
        make_event(
            self.user, Event.EventType.CLASS, title='Maths',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        NotificationService.create_event_notifications(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_notification_title_contains_event_title(self):
        """Test that the notification title contains the event title."""
        make_event(
            self.user, Event.EventType.EXAM, title='Biology Finals',
            delta_start=timezone.timedelta(minutes=30),
            delta_end=timezone.timedelta(minutes=90),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(self.user)
        n = Notification.objects.filter(user=self.user).first()
        self.assertIn('Biology Finals', n.message)