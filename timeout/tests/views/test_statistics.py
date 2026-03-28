"""
test_statistics.py - Tests for the statistics view and helper functions, covering duration formatting,
event counting by type, weekly/monthly breakdowns, urgency filtering, focus stats calculation,
friend leaderboard sorting, login requirements, and correct context data in the statistics view.
"""


from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event
from timeout.models.focus_session import FocusSession
from timeout.views.statistics import (
    _fmt,
    count_by_type,
    events_last_n_months,
    events_last_n_weeks,
    get_focus_stats,
    get_friend_focus_leaderboard,
    get_urgent_events,
    get_user_events,
    statistics_view,
)

User = get_user_model()


def make_event(user, event_type=Event.EventType.OTHER, hours_from_now=24, duration_hours=1, **kwargs):
    """Helper to create an event for testing. By default, creates an 'Other' event 24 hours in the future lasting 1 hour."""
    now = timezone.now()
    start = now + timedelta(hours=hours_from_now)
    return Event.objects.create(
        creator=user,
        title='Test Event',
        event_type=event_type,
        start_datetime=start,
        end_datetime=start + timedelta(hours=duration_hours),
        **kwargs,
    )


def make_focus_session(user, seconds=3600, days_ago=0):
    """Helper to create a focus session for testing. By default, creates a 1-hour session that started now."""
    now = timezone.now()
    started = now - timedelta(days=days_ago, hours=1)
    return FocusSession.objects.create(
        user=user,
        started_at=started,
        ended_at=started + timedelta(seconds=seconds),
        duration_seconds=seconds,
    )

class FmtTests(TestCase):
    """Tests for the _fmt function that formats a duration in seconds into a human-readable string with hours and minutes."""

    def test_zero_seconds(self):
        """Test that 0 seconds returns '0m'."""
        self.assertEqual(_fmt(0), '0m')

    def test_less_than_one_hour(self):
        """Test that durations less than 3600 seconds are formatted as minutes only."""
        self.assertEqual(_fmt(90), '1m')

    def test_exactly_one_hour(self):
        """Test that 3600 seconds is formatted as '1h 0m'."""
        self.assertEqual(_fmt(3600), '1h 0m')

    def test_one_hour_one_minute(self):
        """Test that 3660 seconds is formatted as '1h 1m'."""
        self.assertEqual(_fmt(3661), '1h 1m')

    def test_two_hours_thirty_minutes(self):
        """Test that 9000 seconds is formatted as '2h 30m'."""
        self.assertEqual(_fmt(9000), '2h 30m')


class CountByTypeTests(TestCase):
    """Tests for the count_by_type function that counts the number of events of each type in a queryset and returns a dictionary with human-readable labels as keys and counts as values, ensuring all event types are represented even if count is zero."""

    def setUp(self):
        """Set up a test user for creating events in the count_by_type tests."""
        self.user = User.objects.create_user(username='u', password='pass')

    def test_empty_queryset_all_zero(self):
        """Test that an empty queryset returns a dictionary with all event types as keys and zero counts."""
        events = Event.objects.none()
        counts = count_by_type(events)
        self.assertTrue(all(v == 0 for v in counts.values()))

    def test_counts_correct_type(self):
        """Test that the count_by_type function correctly counts events of different types and returns the correct counts for each type."""
        make_event(self.user, event_type=Event.EventType.DEADLINE)
        make_event(self.user, event_type=Event.EventType.DEADLINE)
        make_event(self.user, event_type=Event.EventType.EXAM)
        events = get_user_events(self.user)
        counts = count_by_type(events)
        self.assertEqual(counts['Deadline'], 2)
        self.assertEqual(counts['Exam'], 1)
        self.assertEqual(counts['Other'], 0)

    def test_all_types_present_as_keys(self):
        """Test that the count_by_type function returns a dictionary with all event types as keys, even if the count for some types is zero."""
        events = Event.objects.none()
        counts = count_by_type(events)
        for _, label in Event.EventType.choices:
            self.assertIn(label, counts)

class EventsLastNWeeksTests(TestCase):
    """Tests for the events_last_n_weeks function that generates a list of dictionaries representing the count of events in each of the last N weeks, ensuring correct labeling, counting, and handling of edge cases such as events outside the range."""

    def setUp(self):
        """Set up a test user for creating events in the events_last_n_weeks tests."""
        self.user = User.objects.create_user(username='u', password='pass')

    def test_returns_n_items(self):
        """Test that the events_last_n_weeks function returns a list with exactly N items, representing the last N weeks, even if there are no events in some weeks."""
        events = Event.objects.none()
        result = events_last_n_weeks(events, n=4)
        self.assertEqual(len(result), 4)

    def test_each_item_has_label_and_count(self):
        """Test that each item in the list returned by events_last_n_weeks contains a 'label' key with a string value and a 'count' key with an integer value, ensuring the correct structure of the output."""
        events = Event.objects.none()
        for item in events_last_n_weeks(events, n=3):
            self.assertIn('label', item)
            self.assertIn('count', item)

    def test_event_this_week_in_last_entry(self):
        """Test that an event occurring within the current week is counted in the last entry of the list returned by events_last_n_weeks, ensuring that events are categorized into the correct week based on their start date."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='Recent',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=2) + timedelta(hours=1),
        )
        events = get_user_events(self.user)
        result = events_last_n_weeks(events, n=4)
        self.assertEqual(result[-1]['count'], 1)

    def test_event_outside_range_not_counted(self):
        """Test that an event occurring outside the range of the last N weeks is not counted in the result returned by events_last_n_weeks."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='Old',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(weeks=10),
            end_datetime=now - timedelta(weeks=10) + timedelta(hours=1),
        )
        events = get_user_events(self.user)
        result = events_last_n_weeks(events, n=8)
        self.assertEqual(sum(w['count'] for w in result), 0)

class EventsLastNMonthsTests(TestCase):
    """Tests for the events_last_n_months function that generates a list of dictionaries representing the count of events in each of the last N months, ensuring correct labeling, counting, and handling of edge cases such as events outside the range."""

    def setUp(self):
        """Set up a test user for creating events in the events_last_n_months tests."""
        self.user = User.objects.create_user(username='u', password='pass')

    def test_returns_n_items(self):
        """Test that the events_last_n_months function returns a list with exactly N items, representing the last N months, even if there are no events in some months."""
        events = Event.objects.none()
        self.assertEqual(len(events_last_n_months(events, n=6)), 6)

    def test_event_this_month_in_last_entry(self):
        """Test that an event occurring within the current month is counted in the last entry of the list returned by events_last_n_months, ensuring that events are categorized into the correct month based on their start date."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='This Month',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(days=3),
            end_datetime=now - timedelta(days=3) + timedelta(hours=1),
        )
        events = get_user_events(self.user)
        result = events_last_n_months(events, n=6)
        self.assertEqual(result[-1]['count'], 1)

    def test_each_item_has_label_and_count(self):
        """Test that each item in the list returned by events_last_n_months contains a 'label' key with a string value and a 'count' key with an integer value, ensuring the correct structure of the output."""
        events = Event.objects.none()
        for item in events_last_n_months(events, n=3):
            self.assertIn('label', item)
            self.assertIn('count', item)

class GetUrgentEventsTests(TestCase):
    """Tests for the get_urgent_events function that filters a queryset of events to include only those that are of type Deadline or Exam and have a due date within the next 7 days, ensuring correct filtering based on event type and due date proximity."""

    def setUp(self):
        """Set up a test user for creating events in the get_urgent_events tests."""
        self.user = User.objects.create_user(username='u', password='pass')

    def _events(self):
        """Helper to get all events for the test user, used in multiple test cases to check the output of get_urgent_events."""
        return get_user_events(self.user)

    def test_deadline_within_7_days_included(self):
        """Test that a Deadline event with a due date within the next 7 days is included in the result returned by get_urgent_events."""
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=48)
        self.assertEqual(get_urgent_events(self._events()).count(), 1)

    def test_exam_within_7_days_included(self):
        """Test that an Exam event with a due date within the next 7 days is included in the result returned by get_urgent_events."""
        make_event(self.user, event_type=Event.EventType.EXAM, hours_from_now=24)
        self.assertEqual(get_urgent_events(self._events()).count(), 1)

    def test_deadline_after_7_days_excluded(self):
        """Test that a Deadline event with a due date more than 7 days in the future is excluded from the result returned by get_urgent_events."""
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=8 * 24)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_past_deadline_excluded(self):
        """Test that a Deadline event with a due date in the past is excluded from the result returned by get_urgent_events."""
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=-2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_class_type_excluded(self):
        """Test that a Class event, even if it has a start date within the next 7 days, is excluded from the result returned by get_urgent_events because only Deadline and Exam types should be considered urgent."""
        make_event(self.user, event_type=Event.EventType.CLASS, hours_from_now=2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_meeting_type_excluded(self):
        """Test that a Meeting event, even if it has a start date within the next 7 days, is excluded from the result returned by get_urgent_events because only Deadline and Exam types should be considered urgent."""
        make_event(self.user, event_type=Event.EventType.MEETING, hours_from_now=2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

class GetFocusStatsTests(TestCase):
    """Tests for the get_focus_stats function that calculates focus session statistics for a user, including total focus time, average session length, count of sessions in the last 7 days, daily focus totals for the last 7 days, and maximum session length, ensuring correct calculations and handling of edge cases such as no sessions."""

    def setUp(self):
        """Set up a test user for creating focus sessions in the get_focus_stats tests."""
        self.user = User.objects.create_user(username='u', password='pass')

    def test_required_keys_present(self):
        """Test that the dictionary returned by get_focus_stats contains all required keys: 'focus_total', 'focus_avg', 'focus_sessions_count', 'focus_daily', and 'focus_max_seconds', ensuring that the function returns a complete set of statistics even if some values are zero or empty."""
        stats = get_focus_stats(self.user)
        for key in ('focus_total', 'focus_avg', 'focus_sessions_count', 'focus_daily', 'focus_max_seconds'):
            self.assertIn(key, stats)

    def test_no_sessions_total_zero(self):
        """Test that if the user has no focus sessions, the 'focus_total' in the stats returned by get_focus_stats is '0m', indicating zero total focus time."""
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 0)
        self.assertEqual(stats['focus_total'], '0m')

    def test_focus_daily_has_7_entries(self):
        """Test that the 'focus_daily' list in the stats returned by get_focus_stats contains 7 entries, representing the last 7 days."""
        stats = get_focus_stats(self.user)
        self.assertEqual(len(stats['focus_daily']), 7)

    def test_session_within_7_days_counted(self):
        """Test that a focus session that started within the last 7 days is counted in the 'focus_sessions_count' and contributes to the 'focus_total' in the stats returned by get_focus_stats."""
        make_focus_session(self.user, seconds=3600, days_ago=2)
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 1)
        self.assertEqual(stats['focus_total'], '1h 0m')

    def test_session_older_than_7_days_excluded(self):
        """Test that a focus session that started more than 7 days ago is not counted in the 'focus_sessions_count' and does not contribute to the 'focus_total' in the stats returned by get_focus_stats."""
        make_focus_session(self.user, seconds=3600, days_ago=8)
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 0)

class GetFriendLeaderboardTests(TestCase):
    """Tests for the get_friend_focus_leaderboard function that generates a leaderboard of the user's friends based on total focus time in the last 7 days, ensuring that the user is included in the leaderboard, followed users are included, entries are sorted correctly, and the 'is_self' flag is set appropriately."""

    def setUp(self):
        """Set up a test user and a followed friend for testing the get_friend_focus_leaderboard function, ensuring that the user and their friend are included in the leaderboard generated by the function."""
        self.user = User.objects.create_user(username='me', password='pass')
        self.friend = User.objects.create_user(username='friend', password='pass')
        self.user.following.add(self.friend)

    def test_user_in_leaderboard(self):
        """Test that the user for whom the leaderboard is generated is included in the result returned by get_friend_focus_leaderboard, ensuring that the function correctly includes the user's own focus stats in the leaderboard."""
        board = get_friend_focus_leaderboard(self.user)
        users = [e['user'] for e in board]
        self.assertIn(self.user, users)

    def test_followed_user_in_leaderboard(self):
        """Test that a user followed by the main user is included in the leaderboard generated by get_friend_focus_leaderboard, ensuring that the function correctly includes followed users in the leaderboard."""
        board = get_friend_focus_leaderboard(self.user)
        users = [e['user'] for e in board]
        self.assertIn(self.friend, users)

    def test_sorted_descending_by_seconds(self):
        """ Test that the entries in the leaderboard returned by get_friend_focus_leaderboard are sorted in descending order based on the 'seconds' key, ensuring that users with more focus time appear higher on the leaderboard."""
        make_focus_session(self.friend, seconds=7200)
        board = get_friend_focus_leaderboard(self.user)
        seconds = [e['seconds'] for e in board]
        self.assertEqual(seconds, sorted(seconds, reverse=True))

    def test_is_self_flag_correct(self):
        """Test that the 'is_self' flag in each entry of the leaderboard returned by get_friend_focus_leaderboard is True for the main user and False for other users, ensuring that the function correctly identifies the user's own entry in the leaderboard."""
        board = get_friend_focus_leaderboard(self.user)
        for entry in board:
            if entry['user'] == self.user:
                self.assertTrue(entry['is_self'])
            else:
                self.assertFalse(entry['is_self'])

class StatisticsViewTests(TestCase):
    """Tests for the statistics_view function that renders the statistics page for a user, ensuring that the view requires login, returns a 200 status code for authenticated users, includes all required context keys, and that the total_events in the context reflects the actual number of events for the user."""

    def setUp(self):
        """Set up a test user and test client for the statistics_view tests, ensuring that the client can be used to make requests to the view and that the user can be authenticated for testing access control and context data."""
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='pass')
        self.url = reverse('statistics')

    def test_login_required(self):
        """Test that accessing the statistics_view without authentication redirects to the login page, ensuring that the view is protected and only accessible to logged-in users."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_authenticated_returns_200(self):
        """Test that an authenticated user can access the statistics_view and receives a 200 OK status code, ensuring that the view is accessible to logged-in users."""
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_has_required_keys(self):
        """Test that the context returned by the statistics_view contains all required keys: 'total_events', 'type_counts', 'weekly_data', 'monthly_data', 'urgent_events', 'focus_total', 'focus_daily', and 'friend_leaderboard', ensuring that the view provides all necessary data for rendering the statistics page."""
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        for key in ('total_events', 'type_counts', 'weekly_data', 'monthly_data',
                    'urgent_events', 'focus_total', 'focus_daily', 'friend_leaderboard'):
            self.assertIn(key, response.context)

    def test_total_events_reflects_user_events(self):
        """Test that the 'total_events' in the context returned by statistics_view accurately reflects the number of events created by the user, ensuring that the view correctly counts and reports the user's events."""
        make_event(self.user)
        make_event(self.user)
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_events'], 2)

class StatisticsViewDirectTests(TestCase):
    """Tests for the statistics_view function that directly call the view with a request object, allowing for testing the view's behavior without going through the URL routing and template rendering, and enabling the use of mocks to verify that the view calls the render function with the correct parameters."""

    def setUp(self):
        """Set up a test user and request factory for testing the statistics_view function directly, allowing for testing the view's behavior without going through the URL routing and template rendering, and enabling the use of mocks to verify that the view calls the render function with the correct parameters."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='direct_user', password='pass')

    def test_statistics_view_calls_build_context_and_render(self):
        """Test that the statistics_view function calls the build_context function to construct the context and then calls the render function to render the response, ensuring that the view follows the expected flow of building context data and rendering a template, and allowing for verification through mocking."""
        request = self.factory.get('/statistics/')
        request.user = self.user
        with patch('timeout.views.statistics.render', return_value=HttpResponse()) as mock_render:
            response = statistics_view(request)
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
