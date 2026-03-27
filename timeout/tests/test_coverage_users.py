"""
Tests for user, settings, profile, and AI calendar coverage.
Covers: settings, profile_edit, profileEditForm, ai_calendar.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.forms.profileEditForm import ProfileEditForm

User = get_user_model()


def make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# Settings View

class SettingsViewTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_settings_get(self):
        resp = self.client.get(reverse('settings'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('appearance_form', resp.context)
        self.assertIn('password_form', resp.context)

    def test_settings_change_password(self):
        resp = self.client.post(reverse('settings'), {
            'action': 'password',
            'old_password': 'TestPass1!',
            'new_password1': 'NewStr0ng@Pass!',
            'new_password2': 'NewStr0ng@Pass!',
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStr0ng@Pass!'))

    def test_settings_change_password_invalid(self):
        resp = self.client.post(reverse('settings'), {
            'action': 'password',
            'old_password': 'WrongPass!',
            'new_password1': 'NewStr0ng@Pass!',
            'new_password2': 'NewStr0ng@Pass!',
        })
        self.assertEqual(resp.status_code, 200)

    def test_settings_delete_account(self):
        resp = self.client.post(reverse('settings'), {'action': 'delete_account'})
        self.assertRedirects(resp, reverse('landing'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_settings_save_ajax(self):
        resp = self.client.post(reverse('settings_save'), {
            'theme': 'dark',
            'colorblind_mode': 'none',
            'notification_sounds': True,
            'pomo_work_minutes': 25,
            'pomo_short_break': 5,
            'pomo_long_break': 15,
            'default_note_category': 'lecture',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])

    def test_settings_save_ajax_invalid(self):
        resp = self.client.post(reverse('settings_save'), {'theme': 'invalid_theme'})
        self.assertEqual(resp.status_code, 400)

    def test_settings_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('settings'))
        self.assertEqual(resp.status_code, 302)


# Profile Edit View

class ProfileEditViewTests(TestCase):

    def setUp(self):
        self.user = make_user(university='Oxford University')
        self.client.login(username='testuser', password='TestPass1!')

    def test_profile_edit_get(self):
        resp = self.client.get(reverse('profile_edit'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)

    def test_profile_edit_post_valid(self):
        resp = self.client.post(reverse('profile_edit'), {
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'My bio',
            'university_choice': 'Cambridge University',
            'year_of_study': 3,
            'academic_interests': 'CS',
            'management_style': 'early_bird',
        })
        self.assertRedirects(resp, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

    def test_profile_edit_post_invalid(self):
        resp = self.client.post(reverse('profile_edit'), {
            'university_choice': '__other__',
            'university_other': '',
        })
        self.assertEqual(resp.status_code, 200)

    def test_profile_edit_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('profile_edit'))
        self.assertEqual(resp.status_code, 302)


# Profile Edit Form

class ProfileEditFormTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_valid_with_known_university(self):
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_valid_with_other_university(self):
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': '__other__',
            'university_other': 'MIT',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_other_requires_text(self):
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': '__other__',
            'university_other': '',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('university_other', form.errors)

    def test_save_sets_university(self):
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': 'Durham University',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.university, 'Durham University')

    def test_save_other_university(self):
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': '__other__',
            'university_other': 'Stanford',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.university, 'Stanford')

    def test_prepopulate_known_university(self):
        self.user.university = 'Oxford University'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), 'Oxford University')

    def test_prepopulate_other_university(self):
        self.user.university = 'Unknown Uni'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), '__other__')
        self.assertEqual(form.initial.get('university_other'), 'Unknown Uni')

    def test_no_university_no_prepopulate(self):
        form = ProfileEditForm(instance=self.user)
        self.assertNotIn('university_choice', form.initial)

    def test_save_without_university_choice(self):
        """When no university is selected, existing value is preserved."""
        self.user.university = 'Existing'
        self.user.save()
        form = ProfileEditForm(data={
            'first_name': 'A', 'last_name': 'B',
            'university_choice': '',
            'year_of_study': 1,
            'management_style': 'early_bird',
        }, instance=self.user)
        if form.is_valid():
            user = form.save()
            self.assertEqual(user.university, 'Existing')


# AI Calendar

class AICalendarTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_empty_input(self):
        resp = self.client.post(reverse('ai_event_create'), {'user_input': ''})
        self.assertEqual(resp.status_code, 400)

    @patch('timeout.views.ai_calendar.settings')
    def test_no_api_key(self, mock_settings):
        mock_settings.OPENAI_API_KEY = ''
        resp = self.client.post(reverse('ai_event_create'), {'user_input': 'meeting tomorrow'})
        self.assertEqual(resp.status_code, 500)

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_json_error(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=MagicMock(side_effect=Exception('fail')))}):
            resp = self.client.post(reverse('ai_event_create'), {'user_input': 'meeting tomorrow'})
            self.assertEqual(resp.status_code, 500)

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_success(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        now = timezone.now()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'title': 'AI Event',
            'event_type': 'meeting',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (now + timedelta(days=1, hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'location': '',
            'description': '',
            'recurrence': 'none',
            'is_all_day': False,
            'visibility': 'private',
        })
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            resp = self.client.post(reverse('ai_event_create'), {'user_input': 'meeting tomorrow at 3pm'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.content)['success'])

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_invalid_json(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'not valid json'
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            resp = self.client.post(reverse('ai_event_create'), {'user_input': 'meeting'})
        self.assertEqual(resp.status_code, 500)

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_all_day_event(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        now = timezone.now()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'title': 'All Day AI',
            'event_type': 'other',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'is_all_day': True,
            'recurrence': 'none',
            'visibility': 'private',
        })
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            resp = self.client.post(reverse('ai_event_create'), {'user_input': 'holiday tomorrow'})
        self.assertEqual(resp.status_code, 200)

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_markdown_code_fence(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        now = timezone.now()
        raw_json = json.dumps({
            'title': 'Fenced',
            'event_type': 'meeting',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (now + timedelta(days=1, hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'recurrence': 'none',
            'is_all_day': False,
            'visibility': 'private',
        })
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = f'```json{raw_json}```'
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            resp = self.client.post(reverse('ai_event_create'), {'user_input': 'test'})
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse('ai_event_create'), {'user_input': 'x'})
        self.assertEqual(resp.status_code, 302)

    def test_requires_post(self):
        resp = self.client.get(reverse('ai_event_create'))
        self.assertEqual(resp.status_code, 405)