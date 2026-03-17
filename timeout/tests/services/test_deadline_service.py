"""
Tests for DeadlineService.get_active_deadlines, DeadlineService.mark_complete,
DeadlineService.get_filtered_deadlines, DeadlineService.get_all_active_events,
and the helper functions _format_timedelta and _format_elapsed.

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
    _format_timedelta,
    _format_elapsed,
)

User = get_user_model()

MOCK_NOW = timezone.make_aware(datetime(2025, 4, 10, 12, 0, 0))


def _patch_now():
    return patch("timeout.services.deadline_service.timezone.now", return_value=MOCK_NOW)


# ======================================================================
# _format_timedelta tests
# ======================================================================


class FormatTimedeltaTests(TestCase):
    """Cover every branch in _format_timedelta."""

    # -- Positive (time remaining) branches --------------------------

    def test_days_and_hours_left(self):
        td = timedelta(days=3, hours=5, minutes=20)
        self.assertEqual(_format_timedelta(td), "3d 5h left")

    def test_hours_and_minutes_left(self):
        td = timedelta(hours=2, minutes=45)
        self.assertEqual(_format_timedelta(td), "2h 45m left")

    def test_minutes_only_left(self):
        td = timedelta(minutes=30)
        self.assertEqual(_format_timedelta(td), "30m left")

    def test_zero_time_left(self):
        td = timedelta(seconds=0)
        self.assertEqual(_format_timedelta(td), "0m left")

    # -- Negative (overdue) branches ---------------------------------

    def test_overdue_days_and_hours(self):
        td = timedelta(days=-2, hours=-3)  # roughly -2d -3h
        result = _format_timedelta(td)
        self.assertIn("overdue", result)
        self.assertIn("d", result)

    def test_overdue_hours_and_minutes(self):
        td = timedelta(hours=-5, minutes=-15)
        result = _format_timedelta(td)
        self.assertIn("overdue", result)
        self.assertIn("h", result)

    def test_overdue_minutes_only(self):
        td = timedelta(minutes=-10)
        result = _format_timedelta(td)
        self.assertEqual(result, "10m overdue")

    def test_overdue_seconds_only_shows_zero_minutes(self):
        td = timedelta(seconds=-30)
        result = _format_timedelta(td)
        self.assertEqual(result, "0m overdue")


# ======================================================================
# _format_elapsed tests
# ======================================================================


class FormatElapsedTests(TestCase):
    """Cover every branch in _format_elapsed."""

    def test_days_ago_singular(self):
        self.assertEqual(_format_elapsed(timedelta(days=1, hours=5)), "Added 1 day ago")

    def test_days_ago_plural(self):
        self.assertEqual(_format_elapsed(timedelta(days=3)), "Added 3 days ago")

    def test_hours_ago_singular(self):
        self.assertEqual(_format_elapsed(timedelta(hours=1, minutes=20)), "Added 1 hour ago")

    def test_hours_ago_plural(self):
        self.assertEqual(_format_elapsed(timedelta(hours=5)), "Added 5 hours ago")

    def test_minutes_ago(self):
        self.assertEqual(_format_elapsed(timedelta(minutes=15)), "Added 15 min ago")

    def test_seconds_ago_shows_just_now(self):
        self.assertEqual(_format_elapsed(timedelta(seconds=30)), "Added just now")

    def test_zero_elapsed_shows_just_now(self):
        self.assertEqual(_format_elapsed(timedelta(seconds=0)), "Added just now")

    def test_negative_elapsed_shows_just_now(self):
        """Negative timedelta (clock skew edge case) → 'Added just now'."""
        self.assertEqual(_format_elapsed(timedelta(seconds=-5)), "Added just now")


# ======================================================================
# DeadlineService.get_active_deadlines tests
# ======================================================================


class GetActiveDeadlinesTests(TestCase):
    """Test DeadlineService.get_active_deadlines with mocked time."""

    def setUp(self):
        self.user = User.objects.create_user(username="svcuser", password="pass1234")

    def _create_deadline(self, title, start_offset, end_offset, completed=False):
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=Event.EventType.DEADLINE,
            start_datetime=MOCK_NOW + start_offset,
            end_datetime=MOCK_NOW + end_offset,
            is_completed=completed,
        )

    # ------------------------------------------------------------------
    # Unauthenticated user → empty list
    # ------------------------------------------------------------------
    def test_unauthenticated_returns_empty(self):
        result = DeadlineService.get_active_deadlines(AnonymousUser())
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # Urgency classification
    # ------------------------------------------------------------------
    @_patch_now()
    def test_overdue_status(self, _mock):
        self._create_deadline("Overdue", timedelta(days=-5), timedelta(hours=-1))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "overdue")

    @_patch_now()
    def test_urgent_status(self, _mock):
        """End time within 24 hours → 'urgent'."""
        self._create_deadline("Urgent", timedelta(days=-1), timedelta(hours=6))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "urgent")

    @_patch_now()
    def test_urgent_boundary_exactly_24h(self, _mock):
        """Exactly 24 hours remaining → 86400 seconds → NOT urgent (> 86400 is false, == triggers 'urgent')."""
        self._create_deadline("Boundary", timedelta(days=-1), timedelta(hours=24))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(results[0]["urgency_status"], "urgent")

    @_patch_now()
    def test_normal_status(self, _mock):
        self._create_deadline("Normal", timedelta(days=-1), timedelta(days=5))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["urgency_status"], "normal")

    # ------------------------------------------------------------------
    # Ordering & filtering
    # ------------------------------------------------------------------
    @_patch_now()
    def test_completed_excluded(self, _mock):
        self._create_deadline("Done", timedelta(days=-1), timedelta(days=2), completed=True)
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(len(results), 0)

    @_patch_now()
    def test_ordered_by_start_datetime(self, _mock):
        self._create_deadline("Later", timedelta(days=1), timedelta(days=10))
        self._create_deadline("Earlier", timedelta(days=-2), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(self.user)
        self.assertEqual(results[0]["event"].title, "Earlier")
        self.assertEqual(results[1]["event"].title, "Later")

    # ------------------------------------------------------------------
    # Display fields populated
    # ------------------------------------------------------------------
    @_patch_now()
    def test_result_dict_structure(self, _mock):
        self._create_deadline("Check", timedelta(days=-1), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(self.user)
        r = results[0]
        self.assertIn("event", r)
        self.assertIn("urgency_status", r)
        self.assertIn("time_remaining", r)
        self.assertIn("time_remaining_display", r)
        self.assertIn("time_elapsed_display", r)

    # ------------------------------------------------------------------
    # Different user sees only own deadlines
    # ------------------------------------------------------------------
    @_patch_now()
    def test_user_isolation(self, _mock):
        other = User.objects.create_user(username="other", password="pass1234")
        self._create_deadline("Mine", timedelta(days=-1), timedelta(days=3))
        results = DeadlineService.get_active_deadlines(other)
        self.assertEqual(len(results), 0)


# ======================================================================
# DeadlineService.mark_complete tests
# ======================================================================


class MarkCompleteServiceTests(TestCase):
    """Test DeadlineService.mark_complete."""

    def setUp(self):
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
        result = DeadlineService.mark_complete(self.user, self.deadline.pk)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_completed)
        self.deadline.refresh_from_db()
        self.assertTrue(self.deadline.is_completed)

    def test_nonexistent_id_returns_none(self):
        result = DeadlineService.mark_complete(self.user, 99999)
        self.assertIsNone(result)

    def test_already_completed_returns_none(self):
        self.deadline.is_completed = True
        self.deadline.save()
        result = DeadlineService.mark_complete(self.user, self.deadline.pk)
        self.assertIsNone(result)

    def test_wrong_user_returns_none(self):
        other = User.objects.create_user(username="stranger", password="pass1234")
        result = DeadlineService.mark_complete(other, self.deadline.pk)
        self.assertIsNone(result)

    def test_non_deadline_event_type_completes(self):
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


# ======================================================================
# DeadlineService.get_filtered_deadlines tests
# ======================================================================


class GetFilteredDeadlinesTests(TestCase):
    """Cover every branch in get_filtered_deadlines."""

    def setUp(self):
        self.user = User.objects.create_user(username="filteruser", password="pass1234")

    def _create_event(self, title, event_type="deadline", end_offset=timedelta(days=3),
                      completed=False, start_offset=timedelta(days=-1)):
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=event_type,
            start_datetime=MOCK_NOW + start_offset,
            end_datetime=MOCK_NOW + end_offset,
            is_completed=completed,
        )

    # -- Unauthenticated user ----------------------------------------
    def test_unauthenticated_returns_empty(self):
        result = DeadlineService.get_filtered_deadlines(AnonymousUser())
        self.assertEqual(result, [])

    # -- Status filters ----------------------------------------------
    @_patch_now()
    def test_active_filter_excludes_completed(self, _m):
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        titles = [r['event'].title for r in results]
        self.assertIn("Active", titles)
        self.assertNotIn("Done", titles)

    @_patch_now()
    def test_completed_filter_shows_only_completed(self, _m):
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='completed')
        titles = [r['event'].title for r in results]
        self.assertNotIn("Active", titles)
        self.assertIn("Done", titles)

    @_patch_now()
    def test_all_filter_shows_everything(self, _m):
        self._create_event("Active", completed=False)
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all')
        self.assertEqual(len(results), 2)

    # -- Event type filter -------------------------------------------
    @_patch_now()
    def test_event_type_filter(self, _m):
        self._create_event("Deadline", event_type="deadline")
        self._create_event("Exam", event_type="exam")
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all', event_type='exam')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['event'].title, "Exam")

    @_patch_now()
    def test_no_event_type_filter_shows_all_types(self, _m):
        self._create_event("Deadline", event_type="deadline")
        self._create_event("Exam", event_type="exam")
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='all', event_type=None)
        self.assertEqual(len(results), 2)

    # -- Sort order --------------------------------------------------
    @_patch_now()
    def test_sort_asc(self, _m):
        self._create_event("Later", end_offset=timedelta(days=5))
        self._create_event("Sooner", end_offset=timedelta(days=1))
        results = DeadlineService.get_filtered_deadlines(self.user, sort_order='asc')
        self.assertEqual(results[0]['event'].title, "Sooner")
        self.assertEqual(results[1]['event'].title, "Later")

    @_patch_now()
    def test_sort_desc(self, _m):
        self._create_event("Later", end_offset=timedelta(days=5))
        self._create_event("Sooner", end_offset=timedelta(days=1))
        results = DeadlineService.get_filtered_deadlines(self.user, sort_order='desc')
        self.assertEqual(results[0]['event'].title, "Later")
        self.assertEqual(results[1]['event'].title, "Sooner")

    # -- Urgency classification --------------------------------------
    @_patch_now()
    def test_completed_urgency_status(self, _m):
        self._create_event("Done", completed=True)
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='completed')
        self.assertEqual(results[0]['urgency_status'], 'completed')

    @_patch_now()
    def test_overdue_urgency_status(self, _m):
        self._create_event("Overdue", end_offset=timedelta(hours=-1))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'overdue')

    @_patch_now()
    def test_urgent_urgency_status(self, _m):
        self._create_event("Urgent", end_offset=timedelta(hours=6))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'urgent')

    @_patch_now()
    def test_normal_urgency_status(self, _m):
        self._create_event("Normal", end_offset=timedelta(days=5))
        results = DeadlineService.get_filtered_deadlines(self.user, status_filter='active')
        self.assertEqual(results[0]['urgency_status'], 'normal')


# ======================================================================
# DeadlineService.get_all_active_events tests
# ======================================================================


class GetAllActiveEventsTests(TestCase):
    """Cover get_all_active_events including type-specific logic."""

    def setUp(self):
        self.user = User.objects.create_user(username="alluser", password="pass1234")

    def _create_event(self, title, event_type="deadline", end_offset=timedelta(days=3),
                      completed=False, start_offset=timedelta(days=-1), status="upcoming"):
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=event_type,
            start_datetime=MOCK_NOW + start_offset,
            end_datetime=MOCK_NOW + end_offset,
            is_completed=completed,
            status=status,
        )

    # -- Unauthenticated ---------------------------------------------
    def test_unauthenticated_returns_empty_dict(self):
        result = DeadlineService.get_all_active_events(AnonymousUser())
        self.assertEqual(result, {})

    # -- Deadline urgency branches -----------------------------------
    @_patch_now()
    def test_deadline_overdue(self, _m):
        self._create_event("Overdue DL", event_type="deadline", end_offset=timedelta(hours=-2))
        result = DeadlineService.get_all_active_events(self.user)
        items = result.get('deadline', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['urgency_status'], 'overdue')

    @_patch_now()
    def test_deadline_urgent(self, _m):
        self._create_event("Urgent DL", event_type="deadline", end_offset=timedelta(hours=6))
        result = DeadlineService.get_all_active_events(self.user)
        items = result.get('deadline', [])
        self.assertEqual(items[0]['urgency_status'], 'urgent')

    @_patch_now()
    def test_deadline_normal(self, _m):
        self._create_event("Normal DL", event_type="deadline", end_offset=timedelta(days=5))
        result = DeadlineService.get_all_active_events(self.user)
        items = result.get('deadline', [])
        self.assertEqual(items[0]['urgency_status'], 'normal')

    # -- Non-deadline: missed vs upcoming ----------------------------
    @_patch_now()
    def test_study_session_missed(self, _m):
        self._create_event("Missed SS", event_type="study_session", end_offset=timedelta(hours=-1))
        result = DeadlineService.get_all_active_events(self.user)
        items = result.get('study_session', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['urgency_status'], 'missed')

    @_patch_now()
    def test_study_session_upcoming(self, _m):
        self._create_event("Future SS", event_type="study_session",
                           start_offset=timedelta(days=1), end_offset=timedelta(days=1, hours=2))
        result = DeadlineService.get_all_active_events(self.user)
        items = result.get('study_session', [])
        self.assertEqual(items[0]['urgency_status'], 'upcoming')

    # -- Completed and cancelled excluded ----------------------------
    @_patch_now()
    def test_completed_excluded(self, _m):
        self._create_event("Completed", completed=True)
        result = DeadlineService.get_all_active_events(self.user)
        self.assertEqual(result, {})

    @_patch_now()
    def test_cancelled_excluded(self, _m):
        self._create_event("Cancelled", status="cancelled")
        result = DeadlineService.get_all_active_events(self.user)
        self.assertEqual(result, {})

    # -- Past non-deadline/non-study-session excluded ----------------
    @_patch_now()
    def test_past_exam_excluded(self, _m):
        self._create_event("Past Exam", event_type="exam", end_offset=timedelta(hours=-1))
        result = DeadlineService.get_all_active_events(self.user)
        self.assertNotIn('exam', result)

    @_patch_now()
    def test_upcoming_exam_included(self, _m):
        self._create_event("Future Exam", event_type="exam",
                           start_offset=timedelta(days=1), end_offset=timedelta(days=1, hours=2))
        result = DeadlineService.get_all_active_events(self.user)
        self.assertIn('exam', result)

    # -- Grouping by type --------------------------------------------
    @_patch_now()
    def test_grouped_by_type(self, _m):
        self._create_event("DL", event_type="deadline", end_offset=timedelta(days=3))
        self._create_event("SS", event_type="study_session",
                           start_offset=timedelta(days=1), end_offset=timedelta(days=1, hours=2))
        result = DeadlineService.get_all_active_events(self.user)
        self.assertIn('deadline', result)
        self.assertIn('study_session', result)