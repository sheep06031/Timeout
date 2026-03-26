from io import StringIO
from unittest.mock import patch, call

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.event import Event
from timeout.models.notification import Notification

User = get_user_model()


def make_deadline(creator, title='Assignment', hours_until_due=12):
    """Helper to create a deadline event due within a given number of hours."""
    now = timezone.now()
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=Event.EventType.DEADLINE,
        start_datetime=now - timezone.timedelta(hours=1),
        end_datetime=now + timezone.timedelta(hours=hours_until_due),
        is_completed=False,
    )


def make_upcoming_event(creator, title='Lecture', event_type=None, hours_until_start=20):
    """Helper to create an upcoming non-deadline event."""
    now = timezone.now()
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=event_type or Event.EventType.CLASS,
        start_datetime=now + timezone.timedelta(hours=hours_until_start),
        end_datetime=now + timezone.timedelta(hours=hours_until_start + 1),
        status=Event.EventStatus.UPCOMING,
        is_completed=False,
    )


class CheckNotificationsCommandTests(TestCase):
    """Tests for the check_notifications management command."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='alice', password='pass123')
        self.user2 = User.objects.create_user(username='bob',   password='pass123')

    def _run(self):
        """Run the management command and return captured stdout."""
        out = StringIO()
        call_command('check_notifications', stdout=out)
        return out.getvalue()

    def test_prints_success_message(self):
        output = self._run()
        self.assertIn('Notifications checked', output)

    def test_creates_deadline_notification_for_user(self):
        make_deadline(self.user1, title='Essay', hours_until_due=12)
        self._run()
        self.assertTrue(
            Notification.objects.filter(
                user=self.user1,
                type=Notification.Type.DEADLINE,
            ).exists()
        )

    def test_creates_deadline_notifications_for_all_users(self):
        make_deadline(self.user1, title='Alice deadline', hours_until_due=12)
        make_deadline(self.user2, title='Bob deadline',   hours_until_due=12)
        self._run()
        self.assertTrue(Notification.objects.filter(user=self.user1, type=Notification.Type.DEADLINE).exists())
        self.assertTrue(Notification.objects.filter(user=self.user2, type=Notification.Type.DEADLINE).exists())

    def test_no_deadline_notification_for_far_future(self):
        make_deadline(self.user1, title='Far away', hours_until_due=200)
        self._run()
        self.assertFalse(Notification.objects.filter(user=self.user1).exists())

    def test_no_deadline_notification_for_completed_event(self):
        event = make_deadline(self.user1, title='Done', hours_until_due=12)
        event.is_completed = True
        event.save()
        self._run()
        self.assertFalse(Notification.objects.filter(user=self.user1).exists())

    def test_no_duplicate_deadline_notifications_on_repeat_run(self):
        make_deadline(self.user1, title='Essay', hours_until_due=12)
        self._run()
        self._run()
        self.assertEqual(
            Notification.objects.filter(user=self.user1, type=Notification.Type.DEADLINE).count(),
            1
        )

    def test_creates_event_notification_for_upcoming_class(self):
        make_upcoming_event(self.user1, title='Maths Lecture', hours_until_start=20)
        self._run()
        self.assertTrue(
            Notification.objects.filter(
                user=self.user1,
                type=Notification.Type.CLASS,
            ).exists()
        )

    def test_creates_event_notifications_for_all_users(self):
        make_upcoming_event(self.user1, title='Alice class', hours_until_start=20)
        make_upcoming_event(self.user2, title='Bob class',   hours_until_start=20)
        self._run()
        self.assertTrue(Notification.objects.filter(user=self.user1, type=Notification.Type.CLASS).exists())
        self.assertTrue(Notification.objects.filter(user=self.user2, type=Notification.Type.CLASS).exists())

    def test_no_event_notification_for_far_future(self):
        make_upcoming_event(self.user1, title='Far lecture', hours_until_start=500)
        self._run()
        self.assertFalse(Notification.objects.filter(user=self.user1).exists())

    def test_no_duplicate_event_notifications_on_repeat_run(self):
        make_upcoming_event(self.user1, title='Maths', hours_until_start=20)
        self._run()
        self._run()
        self.assertEqual(
            Notification.objects.filter(user=self.user1, type=Notification.Type.CLASS).count(),
            1
        )

    def test_no_event_notification_for_completed_event(self):
        event = make_upcoming_event(self.user1, title='Done class', hours_until_start=20)
        event.is_completed = True
        event.save()
        self._run()
        self.assertFalse(Notification.objects.filter(user=self.user1).exists())

    def test_creates_both_deadline_and_event_notifications(self):
        make_deadline(self.user1, title='Assignment', hours_until_due=12)
        make_upcoming_event(self.user1, title='Lecture', hours_until_start=20)
        self._run()
        types = set(Notification.objects.filter(user=self.user1).values_list('type', flat=True))
        self.assertIn(Notification.Type.DEADLINE, types)
        self.assertIn(Notification.Type.CLASS, types)

    def test_runs_with_no_users(self):
        User.objects.all().delete()
        output = self._run()
        self.assertIn('Notifications checked', output)

    def test_runs_with_no_events(self):
        output = self._run()
        self.assertIn('Notifications checked', output)
        self.assertEqual(Notification.objects.count(), 0)

    def test_calls_service_for_every_user(self):
        """Verify the service is called once per user."""
        with patch('timeout.management.commands.check_notifications.NotificationService.create_deadline_notifications') as mock_dl, \
             patch('timeout.management.commands.check_notifications.NotificationService.create_event_notifications') as mock_ev:
            self._run()
            users = list(User.objects.all())
            mock_dl.assert_has_calls([call(u) for u in users], any_order=True)
            mock_ev.assert_has_calls([call(u) for u in users], any_order=True)
            self.assertEqual(mock_dl.call_count, len(users))
            self.assertEqual(mock_ev.call_count, len(users))