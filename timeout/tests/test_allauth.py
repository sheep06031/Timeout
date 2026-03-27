from unittest.mock import MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore

from timeout.adapters import TimeoutAccountAdapter, TimeoutSocialAccountAdapter

from django.contrib.auth.models import AnonymousUser

User = get_user_model()


class TimeoutAccountAdapterTests(TestCase):
    """Tests for the custom AccountAdapter."""

    def setUp(self):
        """Set up test data for TimeoutAccountAdapterTests."""
        self.adapter = TimeoutAccountAdapter()
        self.factory = RequestFactory()

    def test_signup_redirect_sets_flag_and_url(self):
        """Test that get_signup_redirect_url sets the correct session flag and returns the expected URL."""
        request = self.factory.get('/')
        request.session = SessionStore()
        request.session.create()
        url = self.adapter.get_signup_redirect_url(request)
        self.assertEqual(url, '/complete-profile/')
        self.assertTrue(request.session.get('needs_profile_completion'))

    def test_login_redirect_goes_to_dashboard(self):
        """Test that get_login_redirect_url returns the dashboard URL for authenticated users."""
        request = self.factory.get('/')
        request.user = AnonymousUser() 
        url = self.adapter.get_login_redirect_url(request)
        self.assertEqual(url, '/dashboard/')


class TimeoutSocialAccountAdapterTests(TestCase):
    """Tests for the custom SocialAccountAdapter."""

    def setUp(self):
        """Set up test data for TimeoutSocialAccountAdapterTests."""
        self.adapter = TimeoutSocialAccountAdapter()
        self.factory = RequestFactory()

    def test_pre_social_login_links_existing_user_by_email(self):
        """Test that pre_social_login links an existing user by email."""
        user = User.objects.create_user(
            username='existing', email='match@example.com', password='Pass1234!'
        )

        request = self.factory.get('/')
        request.session = SessionStore()

        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'match@example.com'}
        sociallogin.is_existing = False

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, user)

    def test_pre_social_login_skips_if_already_connected(self):
        """Test that pre_social_login does not attempt to connect if the social account is already linked."""
        User.objects.create_user(
            username='existing2', email='connected@example.com', password='Pass1234!'
        )

        request = self.factory.get('/')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'connected@example.com'}
        sociallogin.is_existing = True

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_skips_if_no_email(self):
        """Test that pre_social_login does not attempt to connect if no email is provided in extra_data or email_addresses."""
        request = self.factory.get('/')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {}
        sociallogin.email_addresses = []

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_skips_if_no_matching_user(self):
        """Test that pre_social_login does not attempt to connect if no matching user is found."""
        request = self.factory.get('/')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'nobody@example.com'}
        sociallogin.is_existing = False

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_uses_email_addresses_fallback(self):
        """Test that pre_social_login falls back to email_addresses if extra_data does not contain an email."""
        user = User.objects.create_user(
            username='fallback', email='fallback@example.com', password='Pass1234!'
        )

        request = self.factory.get('/')
        request.session = SessionStore()

        email_obj = MagicMock()
        email_obj.email = 'fallback@example.com'

        sociallogin = MagicMock()
        sociallogin.account.extra_data = {}
        sociallogin.email_addresses = [email_obj]
        sociallogin.is_existing = False

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, user)
