"""
test_password_reset.py - Defines ForgotPasswordViewTests and ResetPasswordViewTests for testing the
two-step password reset flow (request code via email, then verify and reset), covering form validation,
SendGrid email sending, session/code handling, expiry, and password strength checks.
"""


import time

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse

User = get_user_model()


class ForgotPasswordViewTests(TestCase):
    """Tests for the forgot_password view (steps: request and verify)."""

    def setUp(self):
        """Set up a test user and the URL for the forgot password view."""
        self.client = Client()
        self.url = reverse('forgot_password')
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='OldPass123!',
        )

    def test_get_renders_request_step(self):
        """A GET request should render the initial form to enter email/username."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')

    def test_authenticated_user_redirected_to_dashboard(self):
        """If a user is already authenticated, they should be redirected to the dashboard instead of using the forgot password flow."""
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_authenticated_user_post_redirected_to_dashboard(self):
        """Even if an authenticated user tries to POST to the forgot password view, they should be redirected to the dashboard."""
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'testuser'})
        self.assertRedirects(response, reverse('dashboard'))

    def test_empty_identifier_shows_error(self):
        """If the user submits the request form without entering an email or username, an error message should be shown."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Please enter your email or username.', msgs)

    def test_whitespace_only_identifier_shows_error(self):
        """If the user submits the request form with only whitespace in the identifier field, an error message should be shown."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': '   '})
        self.assertEqual(response.status_code, 200)
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Please enter your email or username.', msgs)

    def test_user_not_found_shows_error(self):
        """If no user is found with the provided email or username, an error message should be shown."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'nonexistent@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('No account found with that email or username.', msgs)

    @patch('timeout.views.password_reset.EmailService.send_reset_code', return_value=True)
    def test_lookup_user_by_email(self, mock_send):
        """If the user submits a valid email, the system should look up the user by email and send the reset code."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'testuser@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'verify')
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][0], 'testuser@example.com')

    @patch('timeout.views.password_reset.EmailService.send_reset_code', return_value=True)
    def test_lookup_user_by_username(self, mock_send):
        """If the user submits a valid username, the system should look up the user by username and send the reset code to their email."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'testuser'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'verify')
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[0][0], 'testuser@example.com')

    @patch('timeout.views.password_reset.EmailService.send_reset_code', return_value=False)
    def test_email_send_failure_shows_error(self, mock_send):
        """If sending the reset code email fails, an error message should be shown to the user."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'testuser@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Failed to send the reset code. Please try again later.', msgs)

    @patch('timeout.views.password_reset.EmailService.send_reset_code', return_value=True)
    def test_successful_code_send_stores_session_data(self, mock_send):
        """When the reset code is successfully sent, the session should store the reset code, user ID, and timestamp for later verification."""
        self.client.post(self.url, {'step': 'request', 'identifier': 'testuser@example.com'})
        session = self.client.session
        self.assertIn('reset_code', session)
        self.assertIn('reset_user_id', session)
        self.assertIn('reset_code_time', session)
        self.assertEqual(session['reset_user_id'], self.user.pk)
        # Code should be 6 digits
        self.assertEqual(len(session['reset_code']), 6)
        self.assertTrue(session['reset_code'].isdigit())

    @patch('timeout.views.password_reset.EmailService.send_reset_code', return_value=True)
    def test_successful_code_send_shows_masked_email(self, mock_send):
        """After successfully sending the reset code, the view should show a message that includes the masked email address to which the code was sent."""
        response = self.client.post(self.url, {'step': 'request', 'identifier': 'testuser@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['masked_email'], 'te***@example.com')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('te***@example.com' in m for m in msgs))

    def test_verify_no_stored_code_shows_session_expired(self):
        """If the user tries to verify a code but there is no code stored in the session (e.g. they skipped the request step), they should see a session expired message and be prompted to start over."""
        response = self.client.post(self.url, {'step': 'verify', 'code': '123456'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Session expired. Please start over.', msgs)

    @patch('timeout.views.password_reset.time.time')
    def test_verify_expired_code_shows_error(self, mock_time):
        """If the user tries to verify a code but the current time is past the expiry time (e.g. more than 10 minutes after the code was generated), they should see a code expired message and be prompted to request a new code."""
        session = self.client.session
        session['reset_code'] = '654321'
        session['reset_user_id'] = self.user.pk
        session['reset_code_time'] = 1000.0
        session.save()

        mock_time.return_value = 1000.0 + 601
        response = self.client.post(self.url, {'step': 'verify', 'code': '654321'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'request')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Code has expired. Please request a new one.', msgs)
        session = self.client.session
        self.assertNotIn('reset_code', session)
        self.assertNotIn('reset_user_id', session)
        self.assertNotIn('reset_code_time', session)

    @patch('timeout.views.password_reset.time.time')
    def test_verify_wrong_code_shows_error(self, mock_time):
        """If the user tries to verify a code but enters the wrong code, they should see an invalid code message and be allowed to try again (as long as the code hasn't expired)."""
        session = self.client.session
        session['reset_code'] = '654321'
        session['reset_user_id'] = self.user.pk
        session['reset_code_time'] = 1000.0
        session.save()

        mock_time.return_value = 1000.0 + 100
        response = self.client.post(self.url, {'step': 'verify', 'code': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['step'], 'verify')
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Invalid code. Please try again.', msgs)

    @patch('timeout.views.password_reset.time.time')
    def test_verify_correct_code_redirects_to_reset_password(self, mock_time):
        """If the user enters the correct code and it hasn't expired, they should be redirected to the reset password page and the session should be marked as verified."""
        session = self.client.session
        session['reset_code'] = '654321'
        session['reset_user_id'] = self.user.pk
        session['reset_code_time'] = 1000.0
        session.save()

        mock_time.return_value = 1000.0 + 100  # Not expired
        response = self.client.post(self.url, {'step': 'verify', 'code': '654321'})
        self.assertRedirects(response, reverse('reset_password'))
        session = self.client.session
        self.assertTrue(session.get('reset_verified'))


class ResetPasswordViewTests(TestCase):
    """Tests for the reset_password view (step 3: set new password)."""

    def setUp(self):
        """Set up a test user and the URL for the reset password view."""
        self.client = Client()
        self.url = reverse('reset_password')
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='OldPass123!',
        )

    def _setup_verified_session(self):
        """Helper to set up a session as if the user passed code verification."""
        session = self.client.session
        session['reset_verified'] = True
        session['reset_user_id'] = self.user.pk
        session['reset_code'] = '123456'
        session['reset_code_time'] = time.time()
        session.save()

    def test_authenticated_user_redirected_to_dashboard(self):
        """An authenticated user should not be able to access the reset password page and should be redirected to the dashboard."""
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('dashboard'))

    def test_no_reset_verified_redirects_to_forgot_password(self):
        """If the session does not indicate that the user has passed code verification, they should be redirected to the forgot password page with a message to verify their code first."""
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('forgot_password'))
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Please verify your code first.', msgs)

    def test_no_user_id_redirects_to_forgot_password(self):
        """If the session is missing the reset_user_id (e.g. due to a session issue), the user should be redirected to the forgot password page with a message to start over."""
        session = self.client.session
        session['reset_verified'] = True
        session.save()

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('forgot_password'))
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Session expired. Please start over.', msgs)

    def test_deleted_user_redirects_to_forgot_password(self):
        """If the user ID in the session does not correspond to an existing user (e.g. the user was deleted), the user should be redirected to the forgot password page with a message to start over."""
        session = self.client.session
        session['reset_verified'] = True
        session['reset_user_id'] = 99999
        session.save()

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('forgot_password'))
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('User not found. Please start over.', msgs)

    def test_get_renders_reset_password_form(self):
        """If the session is properly set up with verification and a valid user ID, a GET request should render the reset password form."""
        self._setup_verified_session()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/reset_password.html')

    def test_mismatched_passwords_shows_error(self):
        """If the user submits the form with mismatched passwords, an error message should be shown and the form should be re-rendered."""
        self._setup_verified_session()
        response = self.client.post(self.url, {
            'password1': 'NewPass123!',
            'password2': 'Different123!',
        })
        self.assertEqual(response.status_code, 200)
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Passwords do not match.', msgs)

    @patch('timeout.views.password_reset.validate_password_strength')
    def test_weak_password_shows_error(self, mock_validate):
        """If the user submits a password that fails strength validation, an error message from the validator should be shown and the form should be re-rendered."""
        from django.core.exceptions import ValidationError
        mock_validate.side_effect = ValidationError('Password must be at least 8 characters long.')
        self._setup_verified_session()
        response = self.client.post(self.url, {
            'password1': 'weak',
            'password2': 'weak',
        })
        self.assertEqual(response.status_code, 200)
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Password must be at least 8 characters long.', msgs)

    @patch('timeout.views.password_reset.validate_password_strength')
    def test_successful_password_reset(self, mock_validate):
        """If the user submits valid matching passwords that pass strength validation, their password should be updated, they should be redirected to the landing page, and a success message should be shown."""
        mock_validate.return_value = None  # No error
        self._setup_verified_session()
        new_password = 'NewSecure123!'
        response = self.client.post(self.url, {
            'password1': new_password,
            'password2': new_password,
        })
        self.assertRedirects(response, reverse('landing'))
        msgs = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn('Password reset successfully! You can now log in.', msgs)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    @patch('timeout.views.password_reset.validate_password_strength')
    def test_successful_reset_clears_session_keys(self, mock_validate):
        """After a successful password reset, the session keys related to the reset process should be cleared to prevent reuse."""
        mock_validate.return_value = None
        self._setup_verified_session()
        new_password = 'NewSecure123!'
        self.client.post(self.url, {
            'password1': new_password,
            'password2': new_password,
        })
        session = self.client.session
        self.assertNotIn('reset_code', session)
        self.assertNotIn('reset_user_id', session)
        self.assertNotIn('reset_code_time', session)
        self.assertNotIn('reset_verified', session)
