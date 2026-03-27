from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class ChangeUsernameViewTests(TestCase):
    """Tests for the change_username view, which allows users to update their username from the profile edit page. """

    def setUp(self):
        """Set up a test user and the URL for the change_username view. """
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.url = reverse('change_username')

    def test_get_redirects_to_profile_edit(self):
        """Test that a GET request to the change_username view redirects to the profile edit page, ensuring that the view is only intended to handle POST requests for changing the username and does not render a separate page for GET requests."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('profile_edit'))

    def test_login_required(self):
        """Test that a user must be logged in to access the change_username view, ensuring that the view is protected and only allows authenticated users to change their username."""
        response = self.client.post(self.url, {'new_username': 'newname'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_valid_post_updates_username(self):
        """Test that a valid POST request to the change_username view successfully updates the user's username and redirects to the profile page, ensuring that the view correctly processes valid input and performs the expected update operation."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'brandnewuser'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'brandnewuser')

    def test_invalid_post_redirects_to_profile_edit(self):
        """Test that an invalid POST request (empty username) to the change_username view redirects back to the profile edit page without changing the username, ensuring that the view correctly validates input and handles errors by not performing updates and redirecting appropriately."""
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.assertRedirects(response, reverse('profile_edit'))

    def test_invalid_post_does_not_change_username(self):
        """Test that an invalid POST request (username already taken) to the change_username view does not change the user's username, ensuring that the view correctly prevents updates when the new username is not valid and maintains data integrity."""
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
