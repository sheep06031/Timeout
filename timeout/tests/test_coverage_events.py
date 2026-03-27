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
    """Helper function to create a user with default credentials."""
    return User.objects.create_user(username=username, password=password, **kwargs)


class CalendarViewTests(TestCase):
    """Tests for the calendar view."""

    def setUp(self):
        """Create a test user and log in before each test."""
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_calendar_default(self):
        """Test that the calendar view loads with default parameters."""
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('weeks', resp.context)

    def test_calendar_specific_month(self):
        """Test that the calendar view loads correctly for a specific month."""
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '6'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 6)

    def test_calendar_invalid_params(self):
        """Test that the calendar view handles invalid parameters gracefully."""
        resp = self.client.get(reverse('calendar'), {'year': 'abc', 'month': 'xyz'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_month_before_jan(self):
        """Test that the calendar view handles months before January correctly."""
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 12)
        self.assertEqual(resp.context['year'], 2025)

    def test_calendar_month_after_dec(self):
        """Test that the calendar view handles months after December correctly."""
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '13'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['month'], 1)
        self.assertEqual(resp.context['year'], 2027)

    def test_calendar_with_events(self):
        """Test that the calendar view loads correctly when the user has events."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Test',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_daily(self):
        """Test that the calendar view loads correctly when the user has a daily recurring event."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Daily',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='daily',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_weekly(self):
        """Test that the calendar view loads correctly when the user has a weekly recurring event."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Weekly',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='weekly',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_with_recurring_monthly(self):
        """Test that the calendar view loads correctly when the user has a monthly recurring event."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Monthly',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting', recurrence='monthly',
        )
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 200)

    def test_calendar_prev_next_navigation(self):
        """Test that the calendar view calculates previous and next month/year correctly."""
        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '1'})
        self.assertEqual(resp.context['prev_month'], 12)
        self.assertEqual(resp.context['prev_year'], 2025)

        resp = self.client.get(reverse('calendar'), {'year': '2026', 'month': '12'})
        self.assertEqual(resp.context['next_month'], 1)
        self.assertEqual(resp.context['next_year'], 2027)

    def test_calendar_requires_login(self):
        """Test that the calendar view requires login."""
        self.client.logout()
        resp = self.client.get(reverse('calendar'))
        self.assertEqual(resp.status_code, 302)

class EventCreateTests(TestCase):
    """Tests for the event creation view."""

    def setUp(self):
        """Set up test user and client for event creation tests."""
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_create_event_success(self):
        """Test that creating a new event works successfully."""
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
        """Test that creating an all-day event works successfully."""
        now = timezone.now()
        resp = self.client.post(reverse('event_create'), {
            'title': 'All Day',
            'is_all_day': 'on',
            'start_datetime': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'event_type': 'other',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_event_missing_times(self):
        """Test that creating an event without start and end times redirects."""
        resp = self.client.post(reverse('event_create'), {
            'title': 'No Times',
            'event_type': 'meeting',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_all_day_missing_start(self):
        """Test that creating an all-day event without a start time redirects."""
        resp = self.client.post(reverse('event_create'), {
            'title': 'Bad All Day',
            'is_all_day': 'on',
            'event_type': 'other',
        })
        self.assertEqual(resp.status_code, 302)

    def test_create_requires_login(self):
        """Test that the event creation view requires login."""
        self.client.logout()
        resp = self.client.post(reverse('event_create'), {'title': 'X'})
        self.assertEqual(resp.status_code, 302)

class EventDeleteTests(TestCase):
    """Tests for the event deletion view."""

    def setUp(self):
        """Set up a test user and an event to be deleted before each test."""
        self.user = make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Delete Me',
            start_datetime=now, end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )

    def test_delete_event(self):
        """Test that an event can be deleted successfully."""
        resp = self.client.get(reverse('event_delete', args=[self.event.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_requires_login(self):
        """Test that the event deletion view requires login."""
        self.client.logout()
        resp = self.client.get(reverse('event_delete', args=[self.event.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

class DeadlineServiceTests(TestCase):
    """Tests for the deadline service."""

    def setUp(self):
        """Set up a test user and some deadlines with different urgency statuses before each test."""
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
        """Test that active deadlines are retrieved correctly."""
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 3)
        statuses = {r['urgency_status'] for r in results}
        self.assertIn('normal', statuses)
        self.assertIn('urgent', statuses)
        self.assertIn('overdue', statuses)

    def test_get_active_deadlines_unauthenticated(self):
        """Test that unauthenticated users get an empty list of active deadlines."""
        anon = MagicMock()
        anon.is_authenticated = False
        self.assertEqual(DeadlineService.get_active_deadlines(anon), [])

    def test_mark_complete(self):
        """Test that a deadline can be marked as complete."""
        event = DeadlineService.mark_complete(self.user, self.normal.pk)
        self.assertIsNotNone(event)
        self.assertTrue(event.is_completed)

    def test_mark_complete_not_found(self):
        """Test that marking a non-existent deadline as complete returns None."""
        result = DeadlineService.mark_complete(self.user, 99999)
        self.assertIsNone(result)

    def test_mark_complete_already_completed(self):
        """Test that marking an already completed deadline returns None."""
        self.normal.is_completed = True
        self.normal.save()
        result = DeadlineService.mark_complete(self.user, self.normal.pk)
        self.assertIsNone(result)

    def testtime_string_days(self):
        """Test the time_string function with days."""
        result = time_string(timedelta(days=2, hours=3))
        self.assertIn('2d', result)
        self.assertIn('left', result)

    def testtime_string_hours(self):
        """Test the time_string function with hours."""
        result = time_string(timedelta(hours=5, minutes=30))
        self.assertIn('5h', result)
        self.assertIn('left', result)

    def testtime_string_minutes(self):
        """Test the time_string function with minutes."""
        result = time_string(timedelta(minutes=45))
        self.assertIn('45m', result)

    def testtime_string_overdue_days(self):
        """Test the time_string function with overdue days."""
        result = time_string(timedelta(days=-2, hours=-3))
        self.assertIn('overdue', result)

    def testtime_string_overdue_hours(self):
        """Test the time_string function with overdue hours."""
        result = time_string(timedelta(hours=-5))
        self.assertIn('overdue', result)

    def testtime_string_overdue_minutes(self):
        """Test the time_string function with overdue minutes."""
        result = time_string(timedelta(minutes=-30))
        self.assertIn('overdue', result)

    def testtime_passed_days(self):
        """Test the time_passed function with days."""
        result = time_passed(timedelta(days=3))
        self.assertIn('3 days ago', result)

    def testtime_passed_one_day(self):
        """Test the time_passed function with one day."""
        result = time_passed(timedelta(days=1))
        self.assertIn('1 day ago', result)

    def testtime_passed_hours(self):
        """Test the time_passed function with hours."""
        result = time_passed(timedelta(hours=5))
        self.assertIn('5 hours ago', result)

    def testtime_passed_one_hour(self):
        """Test the time_passed function with one hour."""
        result = time_passed(timedelta(hours=1))
        self.assertIn('1 hour ago', result)

    def testtime_passed_minutes(self):
        """Test the time_passed function with minutes."""
        result = time_passed(timedelta(minutes=15))
        self.assertIn('15 min ago', result)

    def testtime_passed_just_now(self):
        """Test the time_passed function with just now."""
        result = time_passed(timedelta(seconds=30))
        self.assertEqual(result, 'Added just now')

    def testtime_passed_negative(self):
        """Test the time_passed function with negative timedelta."""
        result = time_passed(timedelta(seconds=-5))
        self.assertEqual(result, 'Added just now')


class DeadlineViewTests(TestCase):
    """Tests for the deadline views."""

    def setUp(self):
        """Set up a test user and a deadline before each test."""
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
        """Test that the deadline list view loads and contains deadlines."""
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('deadlines', resp.context)

    def test_deadline_mark_complete(self):
        """Test that marking a deadline as complete works correctly."""
        resp = self.client.post(
            reverse('deadline_mark_complete', args=[self.deadline.pk])
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['is_completed'])

    def test_deadline_mark_complete_not_found(self):
        """Test that marking a non-existent deadline as complete returns a 404 error."""
        resp = self.client.post(
            reverse('deadline_mark_complete', args=[99999])
        )
        self.assertEqual(resp.status_code, 404)

    def test_deadline_requires_login(self):
        """Test that the deadline views require login."""
        self.client.logout()
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 302)