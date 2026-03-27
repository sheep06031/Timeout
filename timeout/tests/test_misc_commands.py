"""
Tests for management commands, email service, and Event model properties.
Covers: check_notifications, init_site, EmailService,
        Event.is_past/is_ongoing/is_upcoming/mark_completed/__str__/save/delete.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from timeout.models import Event, Post
from timeout.services.email_service import EmailService

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# Management Commands

class CheckNotificationsCommandTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_calls_services_for_each_user(self, mock_svc):
        out = StringIO()
        call_command('check_notifications', stdout=out)
        mock_svc.create_deadline_notifications.assert_called_once_with(self.user)
        mock_svc.create_event_notifications.assert_called_once_with(self.user)
        self.assertIn('Notifications checked', out.getvalue())

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_multiple_users(self, mock_svc):
        _make_user('user2')
        out = StringIO()
        call_command('check_notifications', stdout=out)
        self.assertEqual(mock_svc.create_deadline_notifications.call_count, 2)
        self.assertEqual(mock_svc.create_event_notifications.call_count, 2)

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_no_users(self, mock_svc):
        User.objects.all().delete()
        out = StringIO()
        call_command('check_notifications', stdout=out)
        mock_svc.create_deadline_notifications.assert_not_called()
        mock_svc.create_event_notifications.assert_not_called()


class InitSiteCommandTests(TestCase):

    def test_init_site_creates_site(self):
        Site.objects.all().delete()
        out = StringIO()
        call_command('init_site', stdout=out)
        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')
        self.assertEqual(site.name, 'Timeout Local')
        self.assertIn('Created Site', out.getvalue())

    def test_init_site_replaces_existing_site(self):
        Site.objects.all().delete()
        Site.objects.create(id=1, domain='old.example.com', name='Old')
        out = StringIO()
        call_command('init_site', stdout=out)
        self.assertEqual(Site.objects.count(), 1)
        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')

    def test_init_site_idempotent(self):
        Site.objects.all().delete()
        call_command('init_site', stdout=StringIO())
        call_command('init_site', stdout=StringIO())
        self.assertEqual(Site.objects.count(), 1)


# EmailService

class EmailServiceTests(TestCase):

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_success(self, mock_settings):
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'
        mock_sg_instance = MagicMock()
        mock_sg_client = MagicMock(return_value=mock_sg_instance)
        mock_mail_class = MagicMock()
        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=mock_mail_class),
        }):
            result = EmailService.send_reset_code('user@example.com', '123456')
        self.assertTrue(result)
        mock_sg_instance.send.assert_called_once()

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_failure(self, mock_settings):
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception('API error')
        mock_sg_client = MagicMock(return_value=mock_sg_instance)
        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=MagicMock()),
        }):
            result = EmailService.send_reset_code('user@example.com', '999999')
        self.assertFalse(result)

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_logs_on_failure(self, mock_settings):
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception('timeout')
        mock_sg_client = MagicMock(return_value=mock_sg_instance)
        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=MagicMock()),
        }):
            with patch('timeout.services.email_service.logger') as mock_logger:
                EmailService.send_reset_code('user@example.com', '000000')
                mock_logger.error.assert_called_once()


# Event Model Properties

class EventModelPropertyTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.now = timezone.now()

    def _make_event(self, **kwargs):
        defaults = {
            'creator': self.user,
            'title': 'Test Event',
            'event_type': Event.EventType.MEETING,
            'start_datetime': self.now - timedelta(hours=2),
            'end_datetime': self.now + timedelta(hours=2),
            'visibility': Event.Visibility.PRIVATE,
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def test_is_past_true(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertTrue(event.is_past)

    def test_is_past_false_when_ongoing(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_past)

    def test_is_past_false_when_upcoming(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_past)

    def test_is_ongoing_true(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertTrue(event.is_ongoing)

    def test_is_ongoing_false_when_past(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_ongoing)

    def test_is_ongoing_false_when_upcoming(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_ongoing)

    def test_is_upcoming_true(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertTrue(event.is_upcoming)

    def test_is_upcoming_false_when_past(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_upcoming)

    def test_is_upcoming_false_when_ongoing(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_upcoming)

    def test_str(self):
        event = self._make_event(title='My Meeting')
        expected = f"My Meeting ({event.start_datetime.date()})"
        self.assertEqual(str(event), expected)

    def test_mark_completed(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_completed)
        event.mark_completed()
        event.refresh_from_db()
        self.assertTrue(event.is_completed)

    def test_save_public_event_creates_post(self):
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())

    def test_save_public_event_updates_existing_post(self):
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertEqual(Post.objects.filter(event=event).count(), 1)
        event.title = 'Updated Title'
        event.save()
        self.assertEqual(Post.objects.filter(event=event).count(), 1)
        post = Post.objects.get(event=event)
        self.assertIn('Updated Title', post.content)

    def test_save_private_event_no_post(self):
        event = self._make_event(visibility=Event.Visibility.PRIVATE)
        self.assertFalse(Post.objects.filter(event=event).exists())

    def test_save_private_event_deletes_existing_post(self):
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())
        event.visibility = Event.Visibility.PRIVATE
        event.save()
        self.assertFalse(Post.objects.filter(event=event).exists())

    def test_delete_event_removes_linked_posts(self):
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())
        event_pk = event.pk
        event.delete()
        self.assertFalse(Post.objects.filter(event_id=event_pk).exists())

    def test_event_type_exam(self):
        event = self._make_event(event_type=Event.EventType.EXAM)
        self.assertEqual(event.event_type, 'exam')

    def test_event_type_deadline(self):
        event = self._make_event(event_type=Event.EventType.DEADLINE)
        self.assertEqual(event.event_type, 'deadline')

    def test_event_type_class(self):
        event = self._make_event(event_type=Event.EventType.CLASS)
        self.assertEqual(event.event_type, 'class')

    def test_event_type_study_session(self):
        event = self._make_event(event_type=Event.EventType.STUDY_SESSION)
        self.assertEqual(event.event_type, 'study_session')

    def test_event_type_other(self):
        event = self._make_event(event_type=Event.EventType.OTHER)
        self.assertEqual(event.event_type, 'other')


# AI Service

class AIServiceTests(TestCase):

    def test_get_most_productive_day_empty(self):
        from timeout.services.ai_service import _get_most_productive_day
        qs = Event.objects.none()
        result = _get_most_productive_day(qs)
        self.assertEqual(result, 'None yet')

    def test_get_most_productive_day_with_data(self):
        from timeout.services.ai_service import _get_most_productive_day
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Done', event_type='study_session',
            start_datetime=now - timedelta(days=1),
            end_datetime=now - timedelta(days=1) + timedelta(hours=2),
            is_completed=True,
        )
        qs = Event.objects.filter(creator=user)
        result = _get_most_productive_day(qs)
        self.assertNotEqual(result, 'None yet')

    def test_gather_study_stats(self):
        from timeout.services.ai_service import _gather_study_stats
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Study', event_type='study_session',
            start_datetime=now - timedelta(days=1),
            end_datetime=now - timedelta(days=1) + timedelta(hours=3),
            is_completed=True,
        )
        Event.objects.create(
            creator=user, title='Missed DL', event_type='deadline',
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(hours=1),
            is_completed=False,
        )
        stats = _gather_study_stats(user, now)
        self.assertIn('total_study_hours', stats)
        self.assertGreater(stats['total_study_hours'], 0)
        self.assertEqual(stats['missed_deadlines'], 1)


# Sitemaps

class SitemapTests(TestCase):

    def test_sitemap_index(self):
        resp = self.client.get('/sitemap.xml')
        self.assertIn(resp.status_code, [200, 404])


# OAuth Tags

class OAuthTagTests(TestCase):

    def test_google_oauth_available_true(self):
        from timeout.templatetags.oauth_tags import google_oauth_available
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
        app, _ = SocialApp.objects.get_or_create(
            provider='google',
            defaults={'name': 'Google', 'client_id': 'test-id', 'secret': 'x'},
        )
        app.sites.add(Site.objects.get_current())
        result = google_oauth_available()
        self.assertTrue(result)

    def test_google_oauth_available_false(self):
        from timeout.templatetags.oauth_tags import google_oauth_available
        SocialApp = None  # noqa
        result = google_oauth_available()
        self.assertFalse(result)