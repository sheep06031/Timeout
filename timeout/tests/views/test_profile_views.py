"""
test_profile_views.py - Defines ChangeUsernameViewTests for testing the change_username view,
covering GET redirection, login requirements, valid/invalid POST handling, and username update logic.
"""


from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class ChangeUsernameViewTests(TestCase):
    """Tests for the change_username view."""

    def setUp(self):
        """Create a test user and store the change_username URL."""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.url = reverse('change_username')

    def test_get_redirects_to_profile_edit(self):
        """GET requests should redirect to the profile_edit page."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('profile_edit'))

    def test_login_required(self):
        """Unauthenticated POST requests should redirect to the login page."""
        response = self.client.post(self.url, {'new_username': 'newname'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_valid_post_updates_username(self):
        """A valid new username should be saved and the user redirected to their profile."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'brandnewuser'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'brandnewuser')

    def test_invalid_post_redirects_to_profile_edit(self):
        """A duplicate username should redirect back to the profile_edit page."""
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.assertRedirects(response, reverse('profile_edit'))

    def test_invalid_post_does_not_change_username(self):
        """A duplicate username POST should not change the current user's username."""
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
