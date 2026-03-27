"""
Tests for DeadlineService.get_active_deadlines, DeadlineService.mark_complete,
DeadlineService.get_filtered_deadlines, and the helper functions
time_string and time_passed.

All time-dependent tests mock timezone.now() for deterministic results.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone

from timeout.models import Event
from timeout.services.deadline_service import (
    DeadlineService,
    time_string,
    time_passed,
)

User = get_user_model()

MOCK_NOW = timezone.make_aware(datetime(2025, 4, 10, 12, 0, 0))


def _patch_now():
    """Helper to patch timezone.now() to return MOCK_NOW."""
    return patch("timeout.services.deadline_service.timezone.now", return_value=MOCK_NOW)


class FormatTimedeltaTests(TestCase):
    """Cover every branch in time_string."""

    def test_days_and_hours_left(self):
        """Test that days and hours are correctly formatted."""
        td = timedelta(days=3, hours=5, minutes=20)
        self.assertEqual(time_string(td), "3d 5h left")

    def test_hours_and_minutes_left(self):
        """Test that hours and minutes are correctly formatted."""
        td = timedelta(hours=2, minutes=45)
        self.assertEqual(time_string(td), "2h 45m left")

    def test_minutes_only_left(self):
        """Test that minutes only are correctly formatted."""
        td = timedelta(minutes=30)
        self.assertEqual(time_string(td), "30m left")

    def test_zero_time_left(self):
        """Test that zero time left is correctly formatted."""
        td = timedelta(seconds=0)
        self.assertEqual(time_string(td), "0m left")

    def test_overdue_days_and_hours(self):
        """Test that overdue days and hours are correctly formatted."""
        td = timedelta(days=-2, hours=-3)
        result = time_string(td)
        self.assertIn("overdue", result)
        self.assertIn("d", result)

    def test_overdue_hours_and_minutes(self):
        """Test that overdue hours and minutes are correctly formatted."""
        td = timedelta(hours=-5, minutes=-15)
        result = time_string(td)
        self.assertIn("overdue", result)
        self.assertIn("h", result)

    def test_overdue_minutes_only(self):
        """Test that overdue minutes only are correctly formatted."""
        td = timedelta(minutes=-10)
        result = time_string(td)
        self.assertEqual(result, "10m overdue")

    def test_overdue_seconds_only_shows_zero_minutes(self):
        """Test that overdue seconds only are correctly formatted as zero minutes."""
        td = timedelta(seconds=-30)
        result = time_string(td)
        self.assertEqual(result, "0m overdue")


class FormatElapsedTests(TestCase):
    """Cover every branch in time_passed."""

    def test_days_ago_singular(self):
        """Test that singular days are correctly formatted."""
        self.assertEqual(time_passed(timedelta(days=1, hours=5)), "Added 1 day ago")

    def test_days_ago_plural(self):
        """Test that plural days are correctly formatted."""
        self.assertEqual(time_passed(timedelta(days=3)), "Added 3 days ago")

    def test_hours_ago_singular(self):
        """Test that singular hours are correctly formatted."""
        self.assertEqual(time_passed(timedelta(hours=1, minutes=20)), "Added 1 hour ago")

    def test_hours_ago_plural(self):
        """Test that plural hours are correctly formatted."""
        self.assertEqual(time_passed(timedelta(hours=5)), "Added 5 hours ago")

    def test_minutes_ago(self):
        """Test that minutes are correctly formatted."""
        self.assertEqual(time_passed(timedelta(minutes=15)), "Added 15 min ago")

    def test_seconds_ago_shows_just_now(self):
        """Test that seconds are correctly formatted as just now."""
        self.assertEqual(time_passed(timedelta(seconds=30)), "Added just now")

    def test_zero_elapsed_shows_just_now(self):
        """Test that zero elapsed time is correctly formatted as just now."""
        self.assertEqual(time_passed(timedelta(seconds=0)), "Added just now")

    def test_negative_elapsed_shows_just_now(self):
        """Test that negative elapsed time is correctly formatted as just now."""
        self.assertEqual(time_passed(timedelta(seconds=-5)), "Added just now")


class GetActiveDeadlinesTests(TestCase):
    """Test DeadlineService.get_active_deadlines with mocked time."""

    def setUp(self):
        """Set up a test user for DeadlineService tests."""
        self.user = User.objects.create_user(username="svcuser", password="pass1234")

    def _create_deadline(self, title, start_offset, end_offset, completed=False):
        """Helper to create a deadline event with the specified parameters."""
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=Event.EventType.DEADLINE,
            start_datetime=MOCK_NOW + start_offset,
            end_datetime=MOCK_NOW + end_offset,
            is_completed=completed,
        )

    def test_unauthenticated_returns_empty(self):
        """Test that unauthenticated users receive an empty list."""
        result = DeadlineService.get_active_deadlines(AnonymousUser())
        self.assertEqual(result, [])

    @_patch_now()
    def test_overdue_status(self, _mock):
        """Test that overdue deadlines are correctly identified."""
        self._create_deadline("Overdue", timedelta(days=-5), timedelta(hours=-1))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "overdue")

    @_patch_now()
    def test_urgent_status(self, _mock):
        """Test that urgent deadlines are correctly identified."""
        self._create_deadline("Urgent", timedelta(days=-1), timedelta(hours=6))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "urgent")

    @_patch_now()
    def test_urgent_boundary_exactly_24h(self, _mock):
        """Test that deadlines exactly 24 hours away are considered urgent."""
        self._create_deadline("Boundary", timedelta(days=-1), timedelta(hours=24))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(results[0]["urgency_status"], "urgent")

    @_patch_now()
    def test_normal_status(self, _mock):
        """Test that normal deadlines are correctly identified."""
        self._create_deadline("Normal", timedelta(days=-1), timedelta(days=5))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "normal")

    @_patch_now()
    def test_completed_excluded(self, _mock):
        """Test that completed deadlines are excluded from active deadlines."""
        self._create_deadline("Done", timedelta(days=-1), timedelta(days=2), completed=True)
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 0)

    @_patch_now()
    def test_ordered_by_start_datetime(self, _mock):
        """Test that active deadlines are ordered by start datetime."""
        self._create_deadline("Later", timedelta(days=1), timedelta(days=10))
        self._create_deadline("Earlier", timedelta(days=-2), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(results[0]["event"].title, "Earlier")
        self.assertEqual(results[1]["event"].title, "Later")

    @_patch_now()
    def test_result_dict_structure(self, _mock):
        """Test that the result dictionary has the expected structure."""
        self._create_deadline("Check", timedelta(days=-1), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(self.user)
        r = results[0]
        self.assertIn("event", r)
        self.assertIn("urgency_status", r)
        self.assertIn("time_remaining", r)
        self.assertIn("time_remaining_display", r)
        self.assertIn("time_elapsed_display", r)

    @_patch_now()
    def test_user_isolation(self, _mock):
        """Test that users only see their own deadlines."""
        other = User.objects.create_user(username="other", password="pass1234")
        self._create_deadline("Mine", timedelta(days=-1), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(other)
        self.assertEqual(len(results), 0)


class MarkCompleteServiceTests(TestCase):
    """Test DeadlineService.mark_complete."""

    def setUp(self):
        """Set up a test user and deadline for mark_complete tests."""
        self.user = User.objects.create_user(username="markuser", password="pass1234")
        self.deadline = Event.objects.create(
            creator=self.user,
            title="Essay",
            event_type=Event.EventType.DEADLINE,
            start_datetime=MOCK_NOW - timedelta(days=1),
            end_datetime=MOCK_NOW + timedelta(days=2),
            is_completed=False,
        )

    def test_success(self):
        """Test that a deadline can be successfully marked as complete."""
        result = DeadlineService.mark_complete(self.user, self.deadline.pk)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_completed)
        self.deadline.refresh_from_db()
        self.assertTrue(self.deadline.is_completed)

    def test_nonexistent_id_returns_none(self):
        """Test that marking a nonexistent deadline returns None."""
        result = DeadlineService.mark_complete(self.user, 99999)
        self.assertIsNone(result)

    def test_already_completed_returns_none(self):
        """Test that marking an already completed deadline returns None."""
        self.deadline.is_completed = True
        self.deadline.save()
        result = DeadlineService.mark_complete(self.user, self.deadline.pk)
        self.assertIsNone(result)

    def test_wrong_user_returns_none(self):
        """Test that a user cannot mark another user's deadline as complete."""
        other = User.objects.create_user(username="stranger", password="pass1234")
        result = DeadlineService.mark_complete(other, self.deadline.pk)
        self.assertIsNone(result)

    def test_non_deadline_event_type_completes(self):
        """Test that non-deadline event types can be marked as complete."""
        event = Event.objects.create(
            creator=self.user,
            title="Meeting",
            event_type="other",
            start_datetime=MOCK_NOW,
            end_datetime=MOCK_NOW + timedelta(hours=1),
        )
        result = DeadlineService.mark_complete(self.user, event.pk)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_completed)


class GetFilteredDeadlinesTests(TestCase):
    """Cover every branch in get_filtered_deadlines."""

    def setUp(self):
        """Set up a test user for get_filtered_deadlines tests."""
        self.user = User.objects.create_user(username="filteruser", password="pass1234")

    def _create_event(self, title, event_type="deadline", end_offset=timedelta(days=3),completed=False, start_offset=timedelta(days=-1)):
        """Helper to create an event with the specified parameters."""
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=event_type,
            start_datetime=MOCK_NOW + start_offset,
            end_datetime=MOCK_NOW + end_offset,
            is_completed=completed,
        )

    def test_unauthenticated_returns_empty(self):
        """Test that unauthenticated users see no deadlines."""
        result = DeadlineService.get_filtered_deadlines(AnonymousUser())
        self.assertEqual(result, [])

    @_patch_now()
    def test_active_filter_excludes_completed(self, _m):
        """Test that the active filter excludes completed deadlines."""
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        titles = [r['event'].title for r in results]
        self.assertIn("Active", titles)
        self.assertNotIn("Done", titles)

    @_patch_now()
    def test_completed_filter_shows_only_completed(self, _m):
        """Test that the completed filter shows only completed deadlines."""
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='completed')
        titles = [r['event'].title for r in results]
        self.assertNotIn("Active", titles)
        self.assertIn("Done", titles)

    @_patch_now()
    def test_all_filter_shows_everything(self, _m):
        """Test that the all filter shows both completed and active deadlines."""
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all')
        self.assertEqual(len(results), 2)

    @_patch_now()
    def test_event_type_filter(self, _m):
        """Test that filtering by event type works correctly."""
        self._create_event("Deadline", event_type="deadline")
        self._create_event("Exam", event_type="exam")
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all', event_type='exam')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['event'].title, "Exam")

    @_patch_now()
    def test_no_event_type_filter_shows_all_types(self, _m):
        """Test that not specifying an event type filter shows all event types."""
        self._create_event("Deadline", event_type="deadline")
        self._create_event("Exam", event_type="exam")
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all', event_type=None)
        self.assertEqual(len(results), 2)

    @_patch_now()
    def test_sort_asc(self, _m):
        """Test that sorting deadlines in ascending order works correctly."""
        self._create_event("Later", end_offset=timedelta(days=5))
        self._create_event("Sooner", end_offset=timedelta(days=1))
        results = DeadlineService.get_filtered_deadlines(self.user, sort_order='asc')
        self.assertEqual(results[0]['event'].title, "Sooner")
        self.assertEqual(results[1]['event'].title, "Later")

    @_patch_now()
    def test_sort_desc(self, _m):
        """Test that sorting deadlines in descending order works correctly."""
        self._create_event("Later", end_offset=timedelta(days=5))
        self._create_event("Sooner", end_offset=timedelta(days=1))
        results = DeadlineService.get_filtered_deadlines(self.user, sort_order='desc')
        self.assertEqual(results[0]['event'].title, "Later")
        self.assertEqual(results[1]['event'].title, "Sooner")

    @_patch_now()
    def test_completed_urgency_status(self, _m):
        """Test that completed deadlines have 'completed' urgency status."""
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='completed')
        self.assertEqual(results[0]['urgency_status'], 'completed')

    @_patch_now()
    def test_overdue_urgency_status(self, _m):
        """Test that overdue deadlines have 'overdue' urgency status."""
        self._create_event("Overdue", end_offset=timedelta(hours=-1))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'overdue')

    @_patch_now()
    def test_urgent_urgency_status(self, _m):
        """Test that urgent deadlines have 'urgent' urgency status."""
        self._create_event("Urgent", end_offset=timedelta(hours=6))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'urgent')

    @_patch_now()
    def test_normal_urgency_status(self, _m):
        """Test that normal deadlines have 'normal' urgency status."""
        self._create_event("Normal", end_offset=timedelta(days=5))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'normal')
