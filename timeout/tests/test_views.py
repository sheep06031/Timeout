"""
Tests for the views in the timeout app, covering both public and authenticated pages, as well as the signup, login, logout, and complete_profile views.
"""
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from allauth.socialaccount.models import SocialApp

User = get_user_model()


def _create_social_app():
    """Create a dummy Google SocialApp so templates render."""
    app, _ = SocialApp.objects.get_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': 'test-client-id',
            'secret': 'test-secret',
        },
    )
    site = Site.objects.get_current()
    app.sites.add(site)
    return app


class PublicPageTests(TestCase):
    """Tests for pages accessible without authentication."""

    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase - create a SocialApp for templates."""
        _create_social_app()

    def test_landing_page(self):
        """Test that the landing page loads successfully and uses the correct template."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/landing.html')

    def test_login_page(self):
        """Test that the login page loads successfully and uses the correct template."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_signup_page(self):
        """Test that the signup page loads successfully and uses the correct template."""
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/signup.html')


class AuthenticatedPageTests(TestCase):
    """Tests for pages accessible after login."""

    def setUp(self):
        """Set up a test user and log them in for the authenticated page tests."""
        self.user = User.objects.create_user(
            username='pageuser', password='TestPass1!'
        )
        self.client.login(username='pageuser', password='TestPass1!')

    def test_dashboard(self):
        """Test that the dashboard page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_profile(self):
        """Test that the profile page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)

    def test_calendar(self):
        """Test that the calendar page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)

    def test_notes(self):
        """Test that the notes page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('notes'))
        self.assertEqual(response.status_code, 200)

    def test_statistics(self):
        """Test that the statistics page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 200)

    def test_social(self):
        """Test that the social feed page loads successfully for an authenticated user and uses the correct template."""
        response = self.client.get(reverse('social'))
        self.assertEqual(response.status_code, 200)


class SignupViewTests(TestCase):
    """Tests for the signup view logic."""

    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase - create a SocialApp for templates."""
        _create_social_app()

    def test_signup_get_returns_form(self):
        """Test that a GET request to the signup view returns a response containing the signup form."""
        response = self.client.get(reverse('signup'))
        self.assertIn('form', response.context)

    def test_signup_post_valid(self):
        """Test that a POST request with valid data creates a new user and redirects to the complete_profile page."""
        response = self.client.post(reverse('signup'), {
            'email': 'brand@example.com',
            'password1': 'Str0ng@Pass!',
            'password2': 'Str0ng@Pass!',
        })
        # After signup, redirects to complete_profile
        self.assertRedirects(response, reverse('complete_profile'))
        self.assertTrue(User.objects.filter(email='brand@example.com').exists())

    def test_signup_post_logs_user_in(self):
        """Test that after a successful signup, the user is automatically logged in and can access authenticated pages like the dashboard."""
        self.client.post(reverse('signup'), {
            'email': 'auto@example.com',
            'password1': 'Str0ng@Pass!',
            'password2': 'Str0ng@Pass!',
        })
        # User is logged in and can access dashboard
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email='auto@example.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_signup_post_invalid_rerenders(self):
        """Test that a POST request with invalid data (e.g. weak password) does not create a user and re-renders the signup page with errors."""
        response = self.client.post(reverse('signup'), {
            'email': 'bad@example.com',
            'password1': 'short',
            'password2': 'short',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/signup.html')
        self.assertFalse(User.objects.filter(email='bad@example.com').exists())

    def test_signup_redirects_authenticated_user(self):
        """Test that an already authenticated user trying to access the signup page gets redirected to the dashboard."""
        User.objects.create_user(username='already', password='TestPass1!')
        self.client.login(username='already', password='TestPass1!')
        response = self.client.get(reverse('signup'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_signup_sets_session_flag(self):
        """Test that after a successful signup, a session flag 'needs_profile_completion' is set to True to indicate the user needs to complete their profile."""
        self.client.post(reverse('signup'), {
            'email': 'flag@example.com',
            'password1': 'Str0ng@Pass!',
            'password2': 'Str0ng@Pass!',
        })
        self.assertTrue(self.client.session.get('needs_profile_completion'))

    def test_signup_creates_temp_username(self):
        """Test that when a user signs up with an email, a temporary username is created for them that starts with 'user_'."""
        self.client.post(reverse('signup'), {
            'email': 'temp@example.com',
            'password1': 'Str0ng@Pass!',
            'password2': 'Str0ng@Pass!',
        })
        user = User.objects.get(email='temp@example.com')
        self.assertTrue(user.username.startswith('user_'))


class LoginViewTests(TestCase):
    """Tests for the login view logic."""

    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase - create a SocialApp for templates."""
        _create_social_app()

    def setUp(self):
        """Set up a test user for the login tests."""
        self.user = User.objects.create_user(
            username='loginuser', email='login@example.com',
            password='TestPass1!'
        )

    def test_login_get_returns_form(self):
        """Test that a GET request to the login view returns a response containing the login form."""
        response = self.client.get(reverse('login'))
        self.assertIn('form', response.context)

    def test_login_post_valid(self):
        """Test that a POST request with valid credentials logs the user in and redirects to the dashboard."""
        response = self.client.post(reverse('login'), {
            'username': 'login@example.com',
            'password': 'TestPass1!',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_post_valid_with_next(self):
        """Test that a POST request with valid credentials and a 'next' parameter redirects the user to the specified next page after login."""
        url = reverse('login') + '?next=/profile/'
        response = self.client.post(url, {
            'username': 'login@example.com',
            'password': 'TestPass1!',
        })
        self.assertRedirects(response, '/profile/')

    def test_login_post_invalid(self):
        """Test that a POST request with invalid credentials does not log the user in and re-renders the login page with errors."""
        response = self.client.post(reverse('login'), {
            'username': 'login@example.com',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_login_post_nonexistent_email(self):
        """Test that a POST request with a nonexistent email does not log the user in and re-renders the login page with errors."""
        response = self.client.post(reverse('login'), {
            'username': 'nobody@example.com',
            'password': 'TestPass1!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_login_redirects_authenticated_user(self):
        """Test that an already authenticated user trying to access the login page gets redirected to the dashboard."""
        self.client.login(username='loginuser', password='TestPass1!')
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('dashboard'))


class LogoutViewTests(TestCase):
    """Tests for the logout view logic."""

    def setUp(self):
        """Set up a test user and log them in for the logout tests."""
        self.user = User.objects.create_user(
            username='logoutuser', password='TestPass1!'
        )
        self.client.login(username='logoutuser', password='TestPass1!')

    def test_logout_redirects_to_landing(self):
        """Test that a GET request to the logout view logs the user out and redirects to the landing page."""
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('landing'))

    def test_logout_ends_session(self):
        """Test that after a GET request to the logout view, the user's session is ended and they are no longer authenticated."""
        self.client.get(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


class CompleteProfileViewTests(TestCase):
    """Tests for the complete_profile view."""

    @classmethod
    def setUpTestData(cls):
        """Set up data for the whole TestCase - create a SocialApp for templates."""
        _create_social_app()

    def setUp(self):
        """Set up a test user and log them in for the complete_profile tests, also set the session flag needed for access."""
        self.user = User.objects.create_user(
            username='social_user', password='TestPass1!'
        )
        self.client.login(username='social_user', password='TestPass1!')
        # Set session flag - required for complete_profile access
        session = self.client.session
        session['needs_profile_completion'] = True
        session.save()

    def test_complete_profile_get(self):
        """Test that a GET request to the complete_profile view returns a response with the correct template and contains the profile completion form in the context."""
        response = self.client.get(reverse('complete_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/complete_profile.html')
        self.assertIn('form', response.context)

    def test_complete_profile_post_valid(self):
        """Test that a POST request with valid data updates the user's profile and redirects to the dashboard."""
        response = self.client.post(reverse('complete_profile'), {
            'username': 'updated_user',
            'first_name': 'Updated',
            'last_name': 'User',
            'university_choice': 'Oxford University',
            'year_of_study': 2,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.university, 'Oxford University')
        self.assertEqual(self.user.year_of_study, 2)

    def test_complete_profile_post_valid_other_university(self):
        """Test that a POST request with valid data and 'Other' university choice updates the user's profile with the specified other university and redirects to the dashboard."""
        response = self.client.post(reverse('complete_profile'), {
            'username': 'updated_user',
            'first_name': 'Updated',
            'last_name': 'User',
            'university_choice': '__other__',
            'university_other': 'MIT',
            'year_of_study': 3,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.university, 'MIT')

    def test_complete_profile_post_invalid(self):
        """Test that a POST request with invalid data (e.g. missing required fields) does not update the user's profile and re-renders the complete_profile page with errors."""
        response = self.client.post(reverse('complete_profile'), {
            'username': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/complete_profile.html')

    def test_complete_profile_requires_login(self):
        """Test that an unauthenticated user trying to access the complete_profile view gets redirected to the login page."""
        self.client.logout()
        response = self.client.get(reverse('complete_profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_complete_profile_redirects_without_flag(self):
        """Users without the session flag get redirected to dashboard."""
        session = self.client.session
        session.pop('needs_profile_completion', None)
        session.save()
        response = self.client.get(reverse('complete_profile'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_complete_profile_clears_flag(self):
        """Session flag is cleared after successful profile completion."""
        self.client.post(reverse('complete_profile'), {
            'username': 'cleared_user',
            'first_name': 'Cleared',
            'last_name': 'User',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        })
        self.assertFalse(self.client.session.get('needs_profile_completion', False))
