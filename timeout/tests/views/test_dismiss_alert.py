"""
Tests for the dismiss_alert view in the timeout app, including handling of valid and invalid alert keys, duplicate dismissals, and user-specific visibility.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models import DismissedAlert

User = get_user_model()


class DismissAlertViewTest(TestCase):
    """Tests for the dismiss_alert view."""

    def setUp(self):
        """Create a test user, log in, and store the dismiss_alert URL."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.login(username='testuser', password='pass')
        self.url = reverse('dismiss_alert')

    def test_post_valid_key_saves_to_db(self):
        """POSTing a valid alert key should save a DismissedAlert record and return success=True."""
        response = self.client.post(self.url, {'key': 'workload_1_2026-03-26'})
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True})
        self.assertTrue(DismissedAlert.objects.filter(user=self.user, alert_key='workload_1_2026-03-26').exists())

    def test_post_empty_key_returns_400(self):
        """POSTing an empty key should return 400 with success=False."""
        response = self.client.post(self.url, {'key': ''})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'success': False})

    def test_post_missing_key_returns_400(self):
        """POSTing without a key field should return 400."""
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        """GET requests should return 405 Method Not Allowed."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_requires_login(self):
        """Unauthenticated requests should not return 200."""
        self.client.logout()
        response = self.client.post(self.url, {'key': 'workload_1_2026-03-26'})
        self.assertNotEqual(response.status_code, 200)

    def test_duplicate_key_does_not_error(self):
        """Dismissing the same alert key twice should succeed and store only one record."""
        self.client.post(self.url, {'key': 'reschedule_5_missed'})
        response = self.client.post(self.url, {'key': 'reschedule_5_missed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DismissedAlert.objects.filter(user=self.user).count(), 1)

    def test_dismissed_alert_not_visible_to_other_user(self):
        """A dismissal by one user should not appear in another user's dismissed alerts."""
        other_user = User.objects.create_user(username='otheruser', password='pass')
        self.client.post(self.url, {'key': 'deadline_warning_42'})
        keys = set(DismissedAlert.objects.filter(user=other_user).values_list('alert_key', flat=True))
        self.assertNotIn('deadline_warning_42', keys)