"""
Additional tests to increase code coverage to >90%.
Covers: calendar, deadlines, settings, profile, event_delete,
        ai_calendar, profileEditForm, social endpoints, deadline_service.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from allauth.socialaccount.models import SocialApp

from timeout.forms.profileEditForm import ProfileEditForm
from timeout.models import Event
from timeout.services.deadline_service import (
    DeadlineService, _format_timedelta, _format_elapsed,
)

User = get_user_model()


def _setup_social_app():
    app, _ = SocialApp.objects.get_or_create(
        provider='google',
        defaults={'name': 'Google', 'client_id': 'x', 'secret': 'x'},
    )
    app.sites.add(Site.objects.get_current())


def make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# ─── Calendar View ──────────────────────────────────────────────────

class CalendarViewTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_calendar_default(self):
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('weeks', resp.context)

    def test_calendar_specific_month(self):
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '6'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 6)

    def test_calendar_invalid_params(self):
        resp = self.client.get(reverse('calendar'), {'year': 'abc', 'month': 'xyz'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_month_before_jan(self):
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 12)
        self.assertEqual(resp.context['year'], 2025)

    def test_calendar_month_after_dec(self):
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '13'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 1)
        self.assertEqual(resp.context['year'], 2027)

    def test_calendar_with_events(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Test',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_daily(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Daily',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='daily',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_weekly(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Weekly',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='weekly',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_monthly(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Monthly',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='monthly',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_prev_next_navigation(self):
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '1'})
        self.assertEqual(resp.context['prev_month'], 12)
        self.assertEqual(resp.context['prev_year'], 2025)

        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '12'})
        self.assertEqual(resp.context['next_month'], 1)
        self.assertEqual(resp.context['next_year'], 2027)

    def test_calendar_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 302)


# ─── Event Create ───────────────────────────────────────────────────

class EventCreateTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_create_event_success(self):
        now = timezone.now()
        resp = self.client.post(reverse('event_create'), {
            'title': 'New Event',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime': (now + timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'event_type': 'meeting',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Event.objects.filter(title='New Event').exists())

    def test_create_all_day_event(self):
        now = timezone.now()
        resp = self.client.post(reverse('event_create'), {
            'title': 'All Day',
            'is_all_day': 'on',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'event_type': 'other',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_event_missing_times(self):
        resp = self.client.post(reverse('event_create'), {
            'title': 'No Times',
            'event_type': 'meeting',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_all_day_missing_start(self):
        resp = self.client.post(reverse('event_create'), {
            'title': 'Bad All Day',
            'is_all_day': 'on',
            'event_type': 'other',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse('event_create'), {'title': 'X'})
        self.assertEqual(resp.status_code, 302)


# ─── Event Delete ───────────────────────────────────────────────────

class EventDeleteTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Delete Me',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )

    def test_delete_event(self):
        resp = self.client.get(reverse('event_delete', args=[self.event.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('event_delete', args=[self.event.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())


# ─── Deadline Service ───────────────────────────────────────────────

class DeadlineServiceTests(TestCase):

    def setUp(self):
        self.user = make_user()
        now = timezone.now()
        # Normal deadline (>24h away)
        self.normal = Event.objects.create(
            creator=self.user, title='Normal',
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            event_type='deadline',
        )
        # Urgent deadline (<24h away)
        self.urgent = Event.objects.create(
            creator=self.user, title='Urgent',
            start_datetime=now - timedelta(hours=2),
            end_datetime=now + timedelta(hours=12),
            event_type='deadline',
        )
        # Overdue deadline
        self.overdue = Event.objects.create(
            creator=self.user, title='Overdue',
            start_datetime=now - timedelta(days=5),
            end_datetime=now - timedelta(hours=2),
            event_type='deadline',
        )

    def test_get_active_deadlines(self):
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 3)
        statuses = {r['urgency_status'] for r in results}
        self.assertIn('normal', statuses)
        self.assertIn('urgent', statuses)
        self.assertIn('overdue', statuses)

    def test_get_active_deadlines_unauthenticated(self):
        anon = MagicMock()
        anon.is_authenticated = False
        self.assertEqual(DeadlineService.get_active_deadlines(anon), [])

    def test_mark_complete(self):
        event = DeadlineService.mark_complete(self.user, self.normal.pk)
        self.assertIsNotNone(event)
        self.assertTrue(event.is_completed)

    def test_mark_complete_not_found(self):
        result = DeadlineService.mark_complete(self.user, 99999)
        self.assertIsNone(result)

    def test_mark_complete_already_completed(self):
        self.normal.is_completed = True
        self.normal.save()
        result = DeadlineService.mark_complete(self.user, self.normal.pk)
        self.assertIsNone(result)

    def test_format_timedelta_days(self):
        result = _format_timedelta(timedelta(days=2, hours=3))
        self.assertIn('2d', result)
        self.assertIn('left', result)

    def test_format_timedelta_hours(self):
        result = _format_timedelta(timedelta(hours=5, minutes=30))
        self.assertIn('5h', result)
        self.assertIn('left', result)

    def test_format_timedelta_minutes(self):
        result = _format_timedelta(timedelta(minutes=45))
        self.assertIn('45m', result)

    def test_format_timedelta_overdue_days(self):
        result = _format_timedelta(timedelta(days=-2, hours=-3))
        self.assertIn('overdue', result)

    def test_format_timedelta_overdue_hours(self):
        result = _format_timedelta(timedelta(hours=-5))
        self.assertIn('overdue', result)

    def test_format_timedelta_overdue_minutes(self):
        result = _format_timedelta(timedelta(minutes=-30))
        self.assertIn('overdue', result)

    def test_format_elapsed_days(self):
        result = _format_elapsed(timedelta(days=3))
        self.assertIn('3 days ago', result)

    def test_format_elapsed_one_day(self):
        result = _format_elapsed(timedelta(days=1))
        self.assertIn('1 day ago', result)

    def test_format_elapsed_hours(self):
        result = _format_elapsed(timedelta(hours=5))
        self.assertIn('5 hours ago', result)

    def test_format_elapsed_one_hour(self):
        result = _format_elapsed(timedelta(hours=1))
        self.assertIn('1 hour ago', result)

    def test_format_elapsed_minutes(self):
        result = _format_elapsed(timedelta(minutes=15))
        self.assertIn('15 min ago', result)

    def test_format_elapsed_just_now(self):
        result = _format_elapsed(timedelta(seconds=30))
        self.assertEqual(result, 'Added just now')

    def test_format_elapsed_negative(self):
        result = _format_elapsed(timedelta(seconds=-5))
        self.assertEqual(result, 'Added just now')


# ─── Deadline Views ─────────────────────────────────────────────────

class DeadlineViewTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.deadline = Event.objects.create(
            creator=self.user, title='My Deadline',
            start_datetime=now,
            end_datetime=now + timedelta(days=2),
            event_type='deadline',
        )

    def test_deadline_list(self):
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('deadlines', resp.context)

    def test_deadline_mark_complete(self):
        resp = self.client.post(
            reverse('deadline_mark_complete', args=[self.deadline.pk])
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['is_completed'])

    def test_deadline_mark_complete_not_found(self):
        resp = self.client.post(
            reverse('deadline_mark_complete', args=[99999])
        )
        self.assertEqual(resp.status_code, 404)

    def test_deadline_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 302)


# ─── Settings View ──────────────────────────────────────────────────

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
        resp = self.client.post(reverse('settings'), {
            'action': 'delete_account',
        })
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
        resp = self.client.post(reverse('settings_save'), {
            'theme': 'invalid_theme',
        })
        self.assertEqual(resp.status_code, 400)

    def test_settings_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('settings'))
        self.assertEqual(resp.status_code, 302)


# ─── Profile Edit View ──────────────────────────────────────────────

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


# ─── Profile Edit Form ──────────────────────────────────────────────

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


# ─── AI Calendar ────────────────────────────────────────────────────

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
        resp = self.client.post(
            reverse('ai_event_create'), {'user_input': 'meeting tomorrow'}
        )
        self.assertEqual(resp.status_code, 500)

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_json_error(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=MagicMock(side_effect=Exception('fail')))}):
            resp = self.client.post(
                reverse('ai_event_create'), {'user_input': 'meeting tomorrow'}
            )
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
            resp = self.client.post(
                reverse('ai_event_create'), {'user_input': 'meeting tomorrow at 3pm'}
            )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['success'])

    @patch('timeout.views.ai_calendar.settings')
    def test_ai_invalid_json(self, mock_settings):
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'not valid json'
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            resp = self.client.post(
                reverse('ai_event_create'), {'user_input': 'meeting'}
            )
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
            resp = self.client.post(
                reverse('ai_event_create'), {'user_input': 'holiday tomorrow'}
            )
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
            resp = self.client.post(
                reverse('ai_event_create'), {'user_input': 'test'}
            )
        self.assertEqual(resp.status_code, 200)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(
            reverse('ai_event_create'), {'user_input': 'x'}
        )
        self.assertEqual(resp.status_code, 302)

    def test_requires_post(self):
        resp = self.client.get(reverse('ai_event_create'))
        self.assertEqual(resp.status_code, 405)


# ─── Social API Endpoints ───────────────────────────────────────────

class SocialAPITests(TestCase):

    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob', password='TestPass1!')
        self.private_user = make_user('private', password='TestPass1!', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_followers_api(self):
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('users', data)

    def test_following_api(self):
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_own(self):
        resp = self.client.get(reverse('user_followers_api', args=['alice']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_private_denied(self):
        resp = self.client.get(
            reverse('user_followers_api', args=['private'])
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_following_api_own(self):
        resp = self.client.get(reverse('user_following_api', args=['alice']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_denied(self):
        resp = self.client.get(
            reverse('user_following_api', args=['private'])
        )
        self.assertEqual(resp.status_code, 403)

    def test_search_users(self):
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(len(data['users']) >= 1)

    def test_search_users_empty(self):
        resp = self.client.get(reverse('search_users'), {'q': ''})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_users_no_self(self):
        resp = self.client.get(reverse('search_users'), {'q': 'alice'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('alice', usernames)


# ─── Profile View with Events ───────────────────────────────────────

class ProfileEventTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_profile_with_active_event(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Active',
            start_datetime=now - timedelta(minutes=30),
            end_datetime=now + timedelta(minutes=30),
            event_type='meeting',
        )
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)

    def test_profile_with_upcoming_event(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Upcoming',
            start_datetime=now + timedelta(minutes=30),
            end_datetime=now + timedelta(hours=2),
            event_type='meeting',
        )
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)

    def test_profile_with_recent_event(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Recent',
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(minutes=30),
            event_type='meeting',
        )
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)


# ─── Event Edit Edge Cases ──────────────────────────────────────────

class EventEditEdgeCases(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Edit Me',
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )

    def test_edit_all_day(self):
        url = reverse('event_edit', args=[self.event.pk])
        now = timezone.now()
        resp = self.client.post(url, {
            'title': 'All Day Edit',
            'is_all_day': 'on',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'event_type': 'other',
        })
        self.assertEqual(resp.status_code, 302)

    def test_edit_validation_error(self):
        url = reverse('event_edit', args=[self.event.pk])
        resp = self.client.post(url, {
            'title': 'Bad',
            'start_datetime': 'invalid',
            'end_datetime': 'invalid',
            'event_type': 'meeting',
        })
        # Should re-render form or redirect
        self.assertIn(resp.status_code, [200, 302])
