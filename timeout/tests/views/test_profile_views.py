from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class ChangeUsernameViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.url = reverse('change_username')

    # GET redirects to profile_edit (not a POST endpoint)
    def test_get_redirects_to_profile_edit(self):
        self.client.login(username='testuser', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('profile_edit'))

    # Login required
    def test_login_required(self):
        response = self.client.post(self.url, {'new_username': 'newname'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # Valid POST updates username and redirects to profile
    def test_valid_post_updates_username(self):
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'brandnewuser'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'brandnewuser')

    # Invalid POST (duplicate username) redirects to profile_edit
    def test_invalid_post_redirects_to_profile_edit(self):
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        response = self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.assertRedirects(response, reverse('profile_edit'))

    # Invalid POST does not change username
    def test_invalid_post_does_not_change_username(self):
        User.objects.create_user(username='alreadytaken', password='pass123')
        self.client.login(username='testuser', password='pass123')
        self.client.post(self.url, {'new_username': 'alreadytaken'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
