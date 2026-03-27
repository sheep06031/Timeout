"""
Tests for calendar, events, and deadline coverage.
Covers: calendar, event_create, event_delete, deadline_service, deadline_views.
"""
import json
from datetime import timedelta
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event
from timeout.services.deadline_service import DeadlineService, time_string, time_passed

User = get_user_model()


def make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# Calendar View

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


# Event Create

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


# Event Delete

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


# Deadline Service

class DeadlineServiceTests(TestCase):

    def setUp(self):
        self.user = make_user()
        now = timezone.now()
        self.normal = Event.objects.create(
            creator=self.user, title='Normal',
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            event_type='deadline',
        )
        self.urgent = Event.objects.create(
            creator=self.user, title='Urgent',
            start_datetime=now - timedelta(hours=2),
            end_datetime=now + timedelta(hours=12),
            event_type='deadline',
        )
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

    def testtime_string_days(self):
        result = time_string(timedelta(days=2, hours=3))
        self.assertIn('2d', result)
        self.assertIn('left', result)

    def testtime_string_hours(self):
        result = time_string(timedelta(hours=5, minutes=30))
        self.assertIn('5h', result)
        self.assertIn('left', result)

    def testtime_string_minutes(self):
        result = time_string(timedelta(minutes=45))
        self.assertIn('45m', result)

    def testtime_string_overdue_days(self):
        result = time_string(timedelta(days=-2, hours=-3))
        self.assertIn('overdue', result)

    def testtime_string_overdue_hours(self):
        result = time_string(timedelta(hours=-5))
        self.assertIn('overdue', result)

    def testtime_string_overdue_minutes(self):
        result = time_string(timedelta(minutes=-30))
        self.assertIn('overdue', result)

    def testtime_passed_days(self):
        result = time_passed(timedelta(days=3))
        self.assertIn('3 days ago', result)

    def testtime_passed_one_day(self):
        result = time_passed(timedelta(days=1))
        self.assertIn('1 day ago', result)

    def testtime_passed_hours(self):
        result = time_passed(timedelta(hours=5))
        self.assertIn('5 hours ago', result)

    def testtime_passed_one_hour(self):
        result = time_passed(timedelta(hours=1))
        self.assertIn('1 hour ago', result)

    def testtime_passed_minutes(self):
        result = time_passed(timedelta(minutes=15))
        self.assertIn('15 min ago', result)

    def testtime_passed_just_now(self):
        result = time_passed(timedelta(seconds=30))
        self.assertEqual(result, 'Added just now')

    def testtime_passed_negative(self):
        result = time_passed(timedelta(seconds=-5))
        self.assertEqual(result, 'Added just now')


# Deadline Views

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