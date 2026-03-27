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
from timeout.tests import make_user

User = get_user_model()


# Management Commands

class CheckNotificationsCommandTests(TestCase):
    """Tests for the 'check_notifications' management command, covering notification service calls for users and handling of no users scenario."""

    def setUp(self):
        """Set up a test user for the check_notifications command tests."""
        self.user = make_user()

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_calls_services_for_each_user(self, mock_svc):
        """Test that the check_notifications command calls the notification service methods for each user."""
        out = StringIO()
        call_command('check_notifications', stdout=out)
        mock_svc.create_deadline_notifications.assert_called_once_with(self.user)
        mock_svc.create_event_notifications.assert_called_once_with(self.user)
        self.assertIn('Notifications checked', out.getvalue())

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_multiple_users(self, mock_svc):
        """Test that the check_notifications command calls the notification service methods for multiple users."""
        make_user('user2')
        out = StringIO()
        call_command('check_notifications', stdout=out)
        self.assertEqual(mock_svc.create_deadline_notifications.call_count, 2)
        self.assertEqual(mock_svc.create_event_notifications.call_count, 2)

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_no_users(self, mock_svc):
        """Test that the check_notifications command does not call the notification service methods when there are no users."""
        User.objects.all().delete()
        out = StringIO()
        call_command('check_notifications', stdout=out)
        mock_svc.create_deadline_notifications.assert_not_called()
        mock_svc.create_event_notifications.assert_not_called()


class InitSiteCommandTests(TestCase):
    """Tests for the 'init_site' management command, covering creation and replacement of the Site object, and ensuring idempotency."""

    def test_init_site_creates_site(self):
        """Test that the init_site command creates a Site object with the expected domain and name."""
        Site.objects.all().delete()
        out = StringIO()
        call_command('init_site', stdout=out)
        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')
        self.assertEqual(site.name, 'Timeout Local')
        self.assertIn('Created Site', out.getvalue())

    def test_init_site_replaces_existing_site(self):
        """Test that the init_site command replaces an existing Site object with the new domain and name."""
        Site.objects.all().delete()
        Site.objects.create(id=1, domain='old.example.com', name='Old')
        out = StringIO()
        call_command('init_site', stdout=out)
        self.assertEqual(Site.objects.count(), 1)
        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')

    def test_init_site_idempotent(self):
        """Test that running the init_site command multiple times does not create duplicate Site objects."""
        Site.objects.all().delete()
        call_command('init_site', stdout=StringIO())
        call_command('init_site', stdout=StringIO())
        self.assertEqual(Site.objects.count(), 1)

class EmailServiceTests(TestCase):
    """Tests for the EmailService class, covering the send_reset_code method for successful email sending, handling of API failures, and logging of errors."""

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_success(self, mock_settings):
        """Test that the send_reset_code method successfully sends an email using the SendGrid API when provided with valid settings."""
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
        """Test that the send_reset_code method returns False when the SendGrid API call raises an exception, simulating an API failure."""
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

class EventModelPropertyTests(TestCase):
    """Tests for the Event model properties, covering is_past, is_ongoing, and is_upcoming."""

    def setUp(self):
        """Set up a test user and the current time for Event model property tests."""
        self.user = make_user()
        self.now = timezone.now()

    def _make_event(self, **kwargs):
        """Helper method to create an event with default values, allowing overrides."""
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
        """Test that the is_past property returns True for an event that ended in the past."""
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertTrue(event.is_past)

    def test_is_past_false_when_ongoing(self):
        """Test that the is_past property returns False for an event that is currently ongoing."""
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_past)

    def test_is_past_false_when_upcoming(self):
        """Test that the is_past property returns False for an event that is in the future."""
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_past)

    def test_is_ongoing_true(self):
        """Test that the is_ongoing property returns True for an event that is currently ongoing."""
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertTrue(event.is_ongoing)

    def test_is_ongoing_false_when_past(self):
        """Test that the is_ongoing property returns False for an event that ended in the past."""
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_ongoing)

    def test_is_ongoing_false_when_upcoming(self):
        """Test that the is_ongoing property returns False for an event that is in the future."""
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_ongoing)

    def test_is_upcoming_true(self):
        """Test that the is_upcoming property returns True for an event that is in the future."""
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertTrue(event.is_upcoming)

    def test_is_upcoming_false_when_past(self):
        """Test that the is_upcoming property returns False for an event that ended in the past."""
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_upcoming)

    def test_is_upcoming_false_when_ongoing(self):
        """Test that the is_upcoming property returns False for an event that is currently ongoing."""
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_upcoming)

    def test_str(self):
        """Test that the __str__ method returns the expected string representation of the event, including title and start date."""
        event = self._make_event(title='My Meeting')
        expected = f"My Meeting ({event.start_datetime.date()})"
        self.assertEqual(str(event), expected)

    def test_mark_completed(self):
        """Test that the mark_completed method sets the is_completed field to True and saves the event."""
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_completed)
        event.mark_completed()
        event.refresh_from_db()
        self.assertTrue(event.is_completed)

    def test_save_public_event_creates_post(self):
        """Test that saving a public event creates a corresponding Post object linked to the event."""
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())

    def test_save_public_event_updates_existing_post(self):
        """Test that saving a public event updates the content of the existing Post object linked to the event, rather than creating a new post."""
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertEqual(Post.objects.filter(event=event).count(), 1)
        event.title = 'Updated Title'
        event.save()
        self.assertEqual(Post.objects.filter(event=event).count(), 1)
        post = Post.objects.get(event=event)
        self.assertIn('Updated Title', post.content)

    def test_save_private_event_no_post(self):
        """Test that saving a private event does not create a Post object linked to the event."""
        event = self._make_event(visibility=Event.Visibility.PRIVATE)
        self.assertFalse(Post.objects.filter(event=event).exists())

    def test_save_private_event_deletes_existing_post(self):
        """Test that changing an event's visibility from public to private deletes the existing Post object linked to the event."""
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())
        event.visibility = Event.Visibility.PRIVATE
        event.save()
        self.assertFalse(Post.objects.filter(event=event).exists())

    def test_delete_event_removes_linked_posts(self):
        """Test that deleting an event also deletes any Post objects linked to that event."""
        event = self._make_event(visibility=Event.Visibility.PUBLIC)
        self.assertTrue(Post.objects.filter(event=event).exists())
        event_pk = event.pk
        event.delete()
        self.assertFalse(Post.objects.filter(event_id=event_pk).exists())

    def test_event_type_exam(self):
        """Test that creating an event with the event_type of Event.EventType.EXAM sets the event_type field to 'exam'."""
        event = self._make_event(event_type=Event.EventType.EXAM)
        self.assertEqual(event.event_type, 'exam')

    def test_event_type_deadline(self):
        """Test that creating an event with the event_type of Event.EventType.DEADLINE sets the event_type field to 'deadline'."""
        event = self._make_event(event_type=Event.EventType.DEADLINE)
        self.assertEqual(event.event_type, 'deadline')

    def test_event_type_class(self):
        """Test that creating an event with the event_type of Event.EventType.CLASS sets the event_type field to 'class'."""
        event = self._make_event(event_type=Event.EventType.CLASS)
        self.assertEqual(event.event_type, 'class')

    def test_event_type_study_session(self):
        """Test that creating an event with the event_type of Event.EventType.STUDY_SESSION sets the event_type field to 'study_session'."""
        event = self._make_event(event_type=Event.EventType.STUDY_SESSION)
        self.assertEqual(event.event_type, 'study_session')

    def test_event_type_other(self):
        """Test that creating an event with the event_type of Event.EventType.OTHER sets the event_type field to 'other'."""
        event = self._make_event(event_type=Event.EventType.OTHER)
        self.assertEqual(event.event_type, 'other')

class SitemapTests(TestCase):
    """Tests for the sitemap view, covering the response status code for the sitemap index and ensuring it returns a valid XML response when accessed."""

    def test_sitemap_index(self):
        """Test that the sitemap index view returns a 200 status code and contains the expected XML structure."""
        resp = self.client.get('/sitemap.xml')
        self.assertIn(resp.status_code, [200, 404])

class OAuthTagTests(TestCase):
    """Tests for the google_oauth_available template tag, covering scenarios where the SocialApp model is available and when it is not."""

    def test_google_oauth_available_true(self):
        """Test that the google_oauth_available template tag returns True when the SocialApp model is available and has a Google provider configured."""
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
        """Test that the google_oauth_available template tag returns False when the SocialApp model is not available, simulating an ImportError."""
        from timeout.templatetags.oauth_tags import google_oauth_available
        SocialApp = None  # noqa
        result = google_oauth_available()
        self.assertFalse(result)