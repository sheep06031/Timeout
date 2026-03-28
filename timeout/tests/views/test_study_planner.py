"""
test_study_planner.py - Tests for the study planner helper functions (get_busy_slots, get_free_slots,
pick_evenly_spaced_slots, _day_slots, _nearest_slot) and views (plan_sessions, confirm_sessions),
covering scheduling edge cases (overlapping events, minimum gap enforcement, other users' events),
GPT integration, invalid input handling, and authentication checks.
"""


import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event
from timeout.services.study_planner import (
    get_busy_slots,
    get_free_slots,
    pick_evenly_spaced_slots,
    _nearest_slot,
    _day_slots,
)

User = get_user_model()

def _dt(year, month, day, hour=0, minute=0):
    """Helper function to create timezone-aware datetimes for testing."""
    return timezone.make_aware(datetime(year, month, day, hour, minute))

def _make_event(creator, title, start, end, event_type=None, **kwargs):
    """Helper function to create an event for testing."""
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=event_type or Event.EventType.OTHER,
        start_datetime=start,
        end_datetime=end,
        visibility=Event.Visibility.PRIVATE,
        **kwargs,
    )

class GetBusySlotsTests(TestCase):
    """Tests for the get_busy_slots function that retrieves a user's busy time slots within a specified datetime range."""

    def setUp(self):
        """Create a test user for the busy slots tests."""
        self.user = User.objects.create_user(username='busy_u', password='pass')

    def test_no_events_returns_empty(self):
        """If the user has no events in the given time range, get_busy_slots should return an empty list."""
        self.assertEqual(get_busy_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22)), [])

    def test_overlapping_events_returned(self):
        """If the user has events that overlap with the given time range, get_busy_slots should return a list of tuples with the start and end datetimes of those events."""
        e1_start, e1_end = _dt(2026, 4, 1, 9), _dt(2026, 4, 1, 11)
        e2_start, e2_end = _dt(2026, 4, 1, 14), _dt(2026, 4, 1, 16)
        _make_event(self.user, 'E1', e1_start, e1_end)
        _make_event(self.user, 'E2', e2_start, e2_end)
        result = get_busy_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], (e1_start, e1_end))
        self.assertEqual(result[1], (e2_start, e2_end))

    def test_events_outside_window_excluded(self):
        """If the user has events that do not overlap with the given time range, get_busy_slots should not include them in the result."""
        _make_event(self.user, 'Before', _dt(2026, 3, 31, 8), _dt(2026, 3, 31, 10))
        _make_event(self.user, 'After', _dt(2026, 4, 2, 8), _dt(2026, 4, 2, 10))
        self.assertEqual(get_busy_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22)), [])

    def test_other_user_events_excluded(self):
        """If there are events belonging to other users that overlap with the given time range, get_busy_slots should not include them in the result."""
        other = User.objects.create_user(username='other_u', password='pass')
        _make_event(other, 'Not mine', _dt(2026, 4, 1, 10), _dt(2026, 4, 1, 12))
        self.assertEqual(get_busy_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22)), [])


class DaySlotsTests(TestCase):
    """Tests for the _day_slots function that generates free time slots within a day."""

    def test_no_busy_returns_full_day(self):
        """If there are no busy slots, _day_slots should return a single slot covering the entire day."""
        result = _day_slots(_dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), [], 2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start'], '2026-04-01T08:00')
        self.assertEqual(result[0]['end'], '2026-04-01T22:00')

    def test_busy_in_middle_creates_two_slots(self):
        """If there is a busy slot in the middle of the day, _day_slots should return two free slots before and after the busy slot."""
        busy = [(_dt(2026, 4, 1, 12), _dt(2026, 4, 1, 14))]
        result = _day_slots(_dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), busy, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['start'], '2026-04-01T08:00')
        self.assertEqual(result[0]['end'], '2026-04-01T12:00')
        self.assertEqual(result[1]['start'], '2026-04-01T14:00')
        self.assertEqual(result[1]['end'], '2026-04-01T22:00')

    def test_gap_too_small_excluded(self):
        """If there is a busy slot that creates a gap smaller than the minimum session length, _day_slots should not include that gap in the result."""
        busy = [(_dt(2026, 4, 1, 8, 30), _dt(2026, 4, 1, 14))]
        result = _day_slots(_dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), busy, 2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start'], '2026-04-01T14:00')

    def test_busy_outside_day_ignored(self):
        """If there is a busy slot that does not overlap with the given day, _day_slots should ignore it and return the full day as free."""
        busy = [(_dt(2026, 4, 2, 10), _dt(2026, 4, 2, 12))]
        result = _day_slots(_dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), busy, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['start'], '2026-04-01T08:00')
        self.assertEqual(result[0]['end'], '2026-04-01T22:00')

    def test_multiple_busy_slots(self):
        """If there are multiple busy slots throughout the day, _day_slots should return free slots for each gap that meets the minimum session length requirement."""
        busy = [(_dt(2026, 4, 1, 10), _dt(2026, 4, 1, 11)), (_dt(2026, 4, 1, 15), _dt(2026, 4, 1, 17))]
        result = _day_slots(_dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), busy, 1)
        self.assertEqual(len(result), 3)

class GetFreeSlotsTests(TestCase):
    """Tests for the get_free_slots function that retrieves a user's free time slots within a specified datetime range, taking into account their existing events and a minimum session length requirement."""

    def setUp(self):
        """Create a test user for the free slots tests."""
        self.user = User.objects.create_user(username='free_u', password='pass')

    def test_no_busy_returns_full_days(self):
        """If there are no busy slots in the given date range, get_free_slots should return free slots covering each day from 8am to 10pm."""
        result = get_free_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 3, 22), 2)
        self.assertEqual(len(result), 3)

    def test_busy_event_reduces_free_time(self):
        """If there is a busy event that overlaps with one of the days in the given date range, get_free_slots should return free slots for that day that exclude the time occupied by the busy event."""
        _make_event(self.user, 'Meeting', _dt(2026, 4, 1, 12), _dt(2026, 4, 1, 14))
        result = get_free_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), 2)
        self.assertEqual(len(result), 2)

    def test_start_after_8am_skips_day(self):
        """If the start datetime is after 8am on a given day, get_free_slots should not return any free slots for that day since the user would not have enough time to complete a session before the deadline."""
        result = get_free_slots(self.user, _dt(2026, 4, 1, 10), _dt(2026, 4, 1, 22), 1)
        self.assertEqual(result, [])

    def test_min_hours_filters_short_gaps(self):
        """If there are gaps between busy events that are shorter than the minimum session length, get_free_slots should not include those gaps in the result."""
        _make_event(self.user, 'E1', _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 10))
        _make_event(self.user, 'E2', _dt(2026, 4, 1, 11), _dt(2026, 4, 1, 22))
        result = get_free_slots(self.user, _dt(2026, 4, 1, 8), _dt(2026, 4, 1, 22), 2)
        self.assertEqual(result, [])

class NearestSlotTests(TestCase):
    """Tests for the _nearest_slot function that finds the free time slot closest to a given deadline date, while respecting a specified date range and ensuring the slot is not before the deadline."""
    def test_exact_date_found(self):
        """If there is a free slot on the exact date of the deadline, _nearest_slot should return that slot."""
        by_date = {'2026-04-02': [{'start': '2026-04-02T08:00', 'end': '2026-04-02T10:00'}]}
        result = _nearest_slot(by_date, date(2026, 4, 2), date(2026, 4, 5))
        self.assertIsNotNone(result)
        self.assertEqual(result['start'], '2026-04-02T08:00')

    def test_nearby_date_found(self):
        """If there is no free slot on the exact date of the deadline, but there are free slots on nearby dates within the given range, _nearest_slot should return the closest one."""
        by_date = {'2026-04-04': [{'start': '2026-04-04T09:00', 'end': '2026-04-04T11:00'}]}
        result = _nearest_slot(by_date, date(2026, 4, 2), date(2026, 4, 10))
        self.assertIsNotNone(result)
        self.assertEqual(result['start'], '2026-04-04T09:00')

    def test_no_slot_returns_none(self):
        """If there are no free slots on the exact date of the deadline or on any nearby dates within the given range, _nearest_slot should return None."""
        self.assertIsNone(_nearest_slot({}, date(2026, 4, 1), date(2026, 4, 10)))

    def test_candidate_past_deadline_skipped(self):
        """If there is a free slot on a nearby date but it is before the deadline date, _nearest_slot should skip it and continue searching for other candidates."""
        by_date = {'2026-04-10': [{'start': '2026-04-10T08:00', 'end': '2026-04-10T10:00'}]}
        self.assertIsNone(_nearest_slot(by_date, date(2026, 4, 9), date(2026, 4, 9)))

class PickEvenlySpacedSlotsTests(TestCase):
    """Tests for the pick_evenly_spaced_slots function that selects a specified number of slots evenly distributed across a date range."""
    def test_empty_slots_returns_as_is(self):
        """If the input list of slots is empty, pick_evenly_spaced_slots should return an empty list regardless of the number of sessions requested or the date range."""
        self.assertEqual(pick_evenly_spaced_slots([], 3, _dt(2026, 4, 1), _dt(2026, 4, 10)), [])

    def test_zero_or_negative_num_sessions_returns_all(self):
        """If the number of sessions requested is zero or negative, pick_evenly_spaced_slots should return all available slots without filtering."""
        slots = [{'start': '2026-04-01T08:00', 'end': '2026-04-01T10:00'}]
        self.assertEqual(pick_evenly_spaced_slots(slots, 0, _dt(2026, 4, 1), _dt(2026, 4, 10)), slots)
        self.assertEqual(pick_evenly_spaced_slots(slots, -1, _dt(2026, 4, 1), _dt(2026, 4, 10)), slots)

    def test_normal_picks_correct_number(self):
        """If there are enough available slots to choose from, pick_evenly_spaced_slots should return a list of slots that is equal in length to the number of sessions requested."""
        slots = [
            {'start': f'2026-04-0{d}T08:00', 'end': f'2026-04-0{d}T10:00'}
            for d in [1, 3, 5, 7, 9]
        ]
        result = pick_evenly_spaced_slots(slots, 3, _dt(2026, 4, 1), _dt(2026, 4, 10))
        self.assertEqual(len(result), 3)

    def test_picks_are_spread_across_dates(self):
        """If there are enough available slots on different dates, pick_evenly_spaced_slots should return a list of slots that are spread out across the date range rather than clustered on the same date."""
        slots = [
            {'start': '2026-04-02T08:00', 'end': '2026-04-02T10:00'},
            {'start': '2026-04-05T08:00', 'end': '2026-04-05T10:00'},
            {'start': '2026-04-08T08:00', 'end': '2026-04-08T10:00'},
        ]
        result = pick_evenly_spaced_slots(slots, 3, _dt(2026, 4, 1), _dt(2026, 4, 10))
        self.assertEqual(len({s['start'][:10] for s in result}), 3)

    def test_fallback_when_no_chosen(self):
        """If the number of sessions requested is greater than the number of available slots, pick_evenly_spaced_slots should return all available slots without filtering rather than returning an empty list."""
        slots = [{'start': '2026-04-01T08:00', 'end': '2026-04-01T10:00'}]
        result = pick_evenly_spaced_slots(slots, 1, _dt(2026, 4, 1), _dt(2026, 4, 1))
        self.assertGreaterEqual(len(result), 1)

class PlanSessionsViewTests(TestCase):
    """Tests for the plan_sessions view that handles AJAX requests to plan study sessions for a given deadline event, including authentication, input validation, and integration with the study planning logic and GPT scheduling."""

    def setUp(self):
        """Create a test user and set up the test client for the plan_sessions view tests."""
        self.client = Client()
        self.user = User.objects.create_user(username='planner', password='pass')
        self.url = reverse('study_planner_plan')

    def test_auth_and_method_guards(self):
        """The view should require authentication and only allow POST requests. Unauthenticated users should be redirected to the login page, and authenticated users should receive a 405 Method Not Allowed response if they try to access the view with a GET request."""
        resp = self.client.post(self.url, {'event_id': 1})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
        self.client.login(username='planner', password='pass')
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_event_not_found_returns_404(self):
        """If the event_id provided in the POST data does not correspond to an existing event belonging to the authenticated user, the view should return a 404 Not Found response."""
        self.client.login(username='planner', password='pass')
        self.assertEqual(self.client.post(self.url, {'event_id': 99999}).status_code, 404)

    def test_other_users_event_returns_404(self):
        """If the event_id provided in the POST data corresponds to an existing event that belongs to a different user, the view should return a 404 Not Found response rather than exposing the existence of the other user's event."""
        other = User.objects.create_user(username='other', password='pass')
        deadline = _make_event(other, 'Exam', _dt(2026, 4, 10, 10), _dt(2026, 4, 10, 12))
        self.client.login(username='planner', password='pass')
        self.assertEqual(self.client.post(self.url, {'event_id': deadline.pk}).status_code, 404)

    def test_invalid_hours_or_session_length_returns_400(self):
        """If the hours_needed or session_length parameters provided in the POST data are not valid numbers, the view should return a 400 Bad Request response with an appropriate error message."""
        self.client.login(username='planner', password='pass')
        now = timezone.now()
        deadline_dt = (now + timedelta(days=5)).replace(hour=22, minute=0, second=0, microsecond=0)
        deadline = _make_event(self.user, 'Exam', deadline_dt, deadline_dt + timedelta(hours=2))
        resp = self.client.post(self.url, {'event_id': deadline.pk, 'hours_needed': 'abc'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])
        self.assertIn('Invalid', resp.json()['error'])

    def test_fallback_sessions_when_gpt_fails(self):
        """If the call_gpt function returns None or an empty list, the view should fall back to using the candidate slots to create study sessions and return those in the response."""
        self.client.login(username='planner', password='pass')
        now = timezone.now()
        deadline_dt = (now + timedelta(days=5)).replace(hour=22, minute=0, second=0, microsecond=0)
        deadline = _make_event(self.user, 'Mock Exam', deadline_dt, deadline_dt + timedelta(hours=2))
        with patch('timeout.views.study_planner.call_gpt', return_value=None), \
             patch('timeout.views.study_planner.pick_evenly_spaced_slots', return_value=[]):
            resp = self.client.post(self.url, {'event_id': deadline.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['sessions'], [])

    def test_no_free_slots_returns_400(self):
        """If there are no free slots available before the deadline, the view should return a 400 Bad Request response with an appropriate error message rather than returning an empty list of sessions."""
        self.client.login(username='planner', password='pass')
        now = timezone.now()
        deadline = _make_event(self.user, 'Exam', now - timedelta(hours=1), now)
        resp = self.client.post(self.url, {'event_id': deadline.pk, 'hours_needed': '4', 'session_length': '2'})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('No free time', data['error'])

    def test_default_parameters(self):
        """If the hours_needed and session_length parameters are not provided in the POST data, the view should use default values (e.g. 4 hours needed and 2 hour session length) when calculating the study sessions to return in the response."""
        self.client.login(username='planner', password='pass')
        now = timezone.now()
        deadline_dt = (now + timedelta(days=5)).replace(hour=22, minute=0, second=0, microsecond=0)
        deadline = _make_event(self.user, 'Midterm', deadline_dt, deadline_dt + timedelta(hours=2))
        resp = self.client.post(self.url, {'event_id': deadline.pk})
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['sessions']), 2)

class ConfirmSessionsViewTests(TestCase):
    """Tests for the confirm_sessions view that handles AJAX requests to confirm planned study sessions by creating Event objects for each session, including authentication, input validation, and ensuring correct event creation based on the provided session data."""

    def setUp(self):
        """Create a test user and set up the test client for the confirm_sessions view tests."""
        self.client = Client()
        self.user = User.objects.create_user(username='confirmer', password='pass')
        self.url = reverse('study_planner_confirm')

    def test_auth_and_method_guards(self):
        """The view should require authentication and only allow POST requests. Unauthenticated users should be redirected to the login page, and authenticated users should receive a 405 Method Not Allowed response if they try to access the view with a GET request."""
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
        self.client.login(username='confirmer', password='pass')
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_invalid_json_returns_400(self):
        """If the sessions parameter provided in the POST data is not valid JSON, the view should return a 400 Bad Request response with an appropriate error message rather than raising an unhandled exception."""
        self.client.login(username='confirmer', password='pass')
        resp = self.client.post(self.url, {'sessions': '{not valid json'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid session data', resp.json()['error'])

    def test_valid_json_not_list_returns_400(self):
        """If the sessions parameter provided in the POST data is valid JSON but does not decode to a list of session dictionaries, the view should return a 400 Bad Request response with an appropriate error message rather than raising an unhandled exception."""
        self.client.login(username='confirmer', password='pass')
        resp = self.client.post(self.url, {'sessions': '{"key": "value"}'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid session data', resp.json()['error'])

    def test_valid_sessions_create_events(self):
        """If the sessions parameter provided in the POST data is valid JSON that decodes to a list of session dictionaries with the required keys, the view should create new Event objects for each session and return a 200 OK response with a JSON body containing a 'success' key set to True and a 'count' key indicating how many events were created."""
        self.client.login(username='confirmer', password='pass')
        sessions = json.dumps([
            {'title': 'Study for Exam', 'start': '2026-04-05T08:00', 'end': '2026-04-05T10:00'},
            {'title': 'Study for Exam', 'start': '2026-04-07T14:00', 'end': '2026-04-07T16:00'},
        ])
        resp = self.client.post(self.url, {'sessions': sessions})
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 2)
        self.assertEqual(Event.objects.filter(creator=self.user, event_type=Event.EventType.STUDY_SESSION).count(), 2)

    def test_created_events_have_correct_fields(self):
        """Events created by confirming sessions should have the correct title, start and end datetimes, event type set to STUDY_SESSION, visibility set to PRIVATE"""
        self.client.login(username='confirmer', password='pass')
        sessions = json.dumps([{'title': 'Study for Calculus', 'start': '2026-04-05T08:00', 'end': '2026-04-05T10:00'}])
        self.client.post(self.url, {'sessions': sessions})
        event = Event.objects.get(creator=self.user, title='Study for Calculus')
        self.assertEqual(event.event_type, Event.EventType.STUDY_SESSION)
        self.assertEqual(event.visibility, Event.Visibility.PRIVATE)

    def test_missing_keys_skipped(self):
        """If some session dictionaries in the list provided in the POST data are missing required keys (e.g. title, start, or end), the view should skip those sessions and still create events for the valid ones rather than failing the entire request."""
        self.client.login(username='confirmer', password='pass')
        sessions = json.dumps([
            {'title': 'Good', 'start': '2026-04-05T08:00', 'end': '2026-04-05T10:00'},
            {'title': 'Missing end', 'start': '2026-04-06T08:00'},
            {'start': '2026-04-07T08:00', 'end': '2026-04-07T10:00'},
        ])
        data = self.client.post(self.url, {'sessions': sessions}).json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)

    def test_empty_and_invalid_datetime(self):
        """If some session dictionaries in the list provided in the POST data have empty or invalid datetime strings for the start or end keys, the view should skip those sessions and still create events for the valid ones rather than failing the entire request."""
        self.client.login(username='confirmer', password='pass')
        resp = self.client.post(self.url, {'sessions': '[]'})
        self.assertEqual(resp.json()['count'], 0)
        sessions = json.dumps([{'title': 'Bad date', 'start': 'not-a-date', 'end': '2026-04-05T10:00'}])
        resp = self.client.post(self.url, {'sessions': sessions})
        self.assertEqual(resp.json()['count'], 0)

class BuildPromptTests(TestCase):
    """Tests for the build_prompt function that generates a prompt string for the GPT scheduling model based on a deadline event and parameters for hours needed, session length, and candidate free slots."""

    def setUp(self):
        """Create a test user for the build_prompt tests."""
        self.user = User.objects.create_user(username='prompt_u', password='pass')

    def test_returns_string_with_deadline_info(self):
        """The build_prompt function should return a string that includes the title and datetime of the deadline event, as well as the hours needed and session length parameters provided to the function."""
        from timeout.views.study_planner import build_prompt
        deadline = _make_event(self.user, 'Physics Final', _dt(2026, 4, 10, 10, 30), _dt(2026, 4, 10, 12))
        result = build_prompt(deadline, 4, 2, [])
        self.assertIsInstance(result, str)
        self.assertIn('Physics Final', result)
        self.assertIn('2026-04-10 10:30', result)

    def test_contains_session_config(self):
        """The prompt generated by build_prompt should include a clear statement of the hours needed and session length parameters in a format that can be easily parsed by the call_gpt function to determine how many study sessions to recommend and how long each session should be."""
        from timeout.views.study_planner import build_prompt
        deadline = _make_event(self.user, 'Exam', _dt(2026, 4, 10, 10), _dt(2026, 4, 10, 12))
        candidates = [
            {'start': '2026-04-05T08:00', 'end': '2026-04-05T10:00'},
            {'start': '2026-04-07T08:00', 'end': '2026-04-07T10:00'},
            {'start': '2026-04-09T08:00', 'end': '2026-04-09T10:00'},
        ]
        result = build_prompt(deadline, 6, 1.5, candidates)
        self.assertIn('1.5', result)
        self.assertIn('3', result)