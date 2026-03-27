"""
Tests for pages, notifications, notes, deadline list filters,
dashboard greetings, study planner, management commands,
message notifications, sitemaps, and OAuth tags.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event
from timeout.models.message import Conversation, Message

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


def _make_event(user, title='Evt', event_type='meeting', days_offset=1, hours=1, **kwargs):
    now = timezone.now()
    return Event.objects.create(
        creator=user, title=title, event_type=event_type,
        start_datetime=now + timedelta(days=days_offset),
        end_datetime=now + timedelta(days=days_offset, hours=hours),
        **kwargs,
    )


# Pages Views

class PagesViewTests(TestCase):

    def test_banned_page(self):
        resp = self.client.get(reverse('banned'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)


# Notification Service Edge Cases

class NotificationServiceTests(TestCase):

    def test_create_deadline_notifications_within_hour(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Urgent DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(minutes=30),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_deadline_notifications_within_day(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Tomorrow DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(hours=12),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_deadline_notifications_within_week(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='This Week DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_within_hour(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Soon Meeting',
            event_type=Event.EventType.MEETING,
            start_datetime=now + timedelta(minutes=30),
            end_datetime=now + timedelta(hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_tomorrow(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Tomorrow Exam',
            event_type=Event.EventType.EXAM,
            start_datetime=now + timedelta(hours=12),
            end_datetime=now + timedelta(hours=14),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_this_week(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='This Week Class',
            event_type=Event.EventType.CLASS,
            start_datetime=now + timedelta(days=3),
            end_datetime=now + timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_far_future_ignored(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Far Away',
            event_type=Event.EventType.MEETING,
            start_datetime=now + timedelta(days=30),
            end_datetime=now + timedelta(days=30, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertFalse(Notification.objects.filter(user=user).exists())

    def test_notify_once_no_duplicate(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        event = Event.objects.create(
            creator=user, title='DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(minutes=30),
            is_completed=False,
        )
        NotificationService._notify_once(user, event, "Test msg")
        NotificationService._notify_once(user, event, "Test msg")
        self.assertEqual(Notification.objects.filter(user=user, message="Test msg").count(), 1)


# Notes Autosave and Edit

class NoteAutosaveTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        from timeout.models import Note
        self.note = Note.objects.create(
            owner=self.user, title='Test Note', content='Initial content',
        )

    def test_autosave(self):
        resp = self.client.post(reverse('note_autosave', args=[self.note.id]), {
            'title': 'Updated Title',
            'content': 'Updated content',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'ok')

    def test_autosave_with_count_edit(self):
        resp = self.client.post(reverse('note_autosave', args=[self.note.id]), {
            'title': 'Updated',
            'content': 'Updated',
            'count_edit': '1',
        })
        self.assertEqual(resp.status_code, 200)

    def test_note_edit_page(self):
        resp = self.client.get(reverse('note_edit', args=[self.note.id]))
        self.assertEqual(resp.status_code, 200)


# Deadline List View with Filters

class DeadlineListFilterTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Active DL',
            event_type='deadline',
            start_datetime=now, end_datetime=now + timedelta(days=3),
        )
        Event.objects.create(
            creator=self.user, title='Done DL',
            event_type='deadline',
            start_datetime=now - timedelta(days=5),
            end_datetime=now - timedelta(days=1),
            is_completed=True,
        )

    def test_deadline_list_default(self):
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_completed_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'status': 'completed'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_all_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'status': 'all'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_sort_desc(self):
        resp = self.client.get(reverse('deadline_list'), {'sort': 'desc'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_type_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'type': 'deadline'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_invalid_type_ignored(self):
        resp = self.client.get(reverse('deadline_list'), {'type': 'bogus_type'})
        self.assertEqual(resp.status_code, 200)


# Pages: Landing, Dashboard greeting branches

class LandingPageTests(TestCase):

    def test_landing_unauthenticated(self):
        resp = self.client.get(reverse('landing'))
        self.assertEqual(resp.status_code, 200)

    def test_landing_authenticated_redirects_dashboard(self):
        _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        resp = self.client.get(reverse('landing'))
        self.assertRedirects(resp, reverse('dashboard'))


class DashboardGreetingTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    @patch('timeout.views.pages.timezone')
    def test_morning_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 9, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    @patch('timeout.views.pages.timezone')
    def test_afternoon_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 14, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    @patch('timeout.views.pages.timezone')
    def test_evening_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 20, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)


# Study Planner: call_gpt

class CallGptTests(TestCase):

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_success(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {'title': 'Study for Essay', 'start': '2026-04-01T10:00', 'end': '2026-04-01T12:00'}
        ])
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            result = call_gpt(deadline, 4, 2, [{'date': '2026-04-01', 'start': '10:00', 'end': '18:00'}])
        self.assertIsInstance(result, list)

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_exception_raises(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=MagicMock(side_effect=Exception('fail')))}):
            with self.assertRaises(Exception):
                call_gpt(deadline, 4, 2, [])

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_markdown_fence(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        raw_json = json.dumps([{'title': 'Study', 'start': '2026-04-01T10:00', 'end': '2026-04-01T12:00'}])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = f'```json{raw_json}```'
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            result = call_gpt(deadline, 4, 2, [])
        self.assertIsInstance(result, list)


# Management Command: check_site

class CheckSiteCommandTests(TestCase):

    def test_check_site_runs(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('check_site', stdout=out)
        self.assertIn('SITE_ID', out.getvalue())


# Notification Service: create_message_notification

class MessageNotificationTests(TestCase):

    def test_create_message_notification(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        alice = _make_user('alice')
        bob = _make_user('bob')
        conv = Conversation.objects.create()
        conv.participants.add(alice, bob)
        msg = Message.objects.create(conversation=conv, sender=alice, content='Hi')
        NotificationService.create_message_notification(bob, msg)
        self.assertTrue(Notification.objects.filter(user=bob).exists())

    def test_create_message_notification_no_recipient(self):
        from timeout.services.notification_service import NotificationService
        alice = _make_user('alice')
        conv = Conversation.objects.create()
        conv.participants.add(alice)
        msg = Message.objects.create(conversation=conv, sender=alice, content='Solo')
        NotificationService.create_message_notification(alice, msg)