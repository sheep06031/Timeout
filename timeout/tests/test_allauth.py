from unittest.mock import MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore

from timeout.adapters import TimeoutAccountAdapter, TimeoutSocialAccountAdapter

User = get_user_model()


class TimeoutAccountAdapterTests(TestCase):
    """Tests for the custom AccountAdapter."""

    def setUp(self):
        self.adapter = TimeoutAccountAdapter()
        self.factory = RequestFactory()

    def test_signup_redirect_sets_flag_and_url(self):
        request = self.factory.get('/')
        request.session = SessionStore()
        request.session.create()
        url = self.adapter.get_signup_redirect_url(request)
        self.assertEqual(url, '/complete-profile/')
        self.assertTrue(request.session.get('needs_profile_completion'))

    def test_login_redirect_goes_to_dashboard(self):
        request = self.factory.get('/')
        url = self.adapter.get_login_redirect_url(request)
        self.assertEqual(url, '/dashboard/')


class TimeoutSocialAccountAdapterTests(TestCase):
    """Tests for the custom SocialAccountAdapter."""

    def setUp(self):
        self.adapter = TimeoutSocialAccountAdapter()
        self.factory = RequestFactory()

    def test_pre_social_login_links_existing_user_by_email(self):
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
        request = self.factory.get('/')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {}
        sociallogin.email_addresses = []

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_skips_if_no_matching_user(self):
        request = self.factory.get('/')
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {'email': 'nobody@example.com'}
        sociallogin.is_existing = False

        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_uses_email_addresses_fallback(self):
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
