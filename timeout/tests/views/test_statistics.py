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
    now = timezone.now()
    start = now + timedelta(hours=hours_from_now)
    return Event.objects.create(
        creator=user,
        title='Test Event',
        event_type=event_type,
        start_datetime=start,
        end_datetime=start + timedelta(hours=duration_hours),
        allow_conflict=True,
        **kwargs,
    )


def make_focus_session(user, seconds=3600, days_ago=0):
    now = timezone.now()
    started = now - timedelta(days=days_ago, hours=1)
    return FocusSession.objects.create(
        user=user,
        started_at=started,
        ended_at=started + timedelta(seconds=seconds),
        duration_seconds=seconds,
    )


# _fmt
class FmtTests(TestCase):

    def test_zero_seconds(self):
        self.assertEqual(_fmt(0), '0m')

    def test_less_than_one_hour(self):
        self.assertEqual(_fmt(90), '1m')

    def test_exactly_one_hour(self):
        self.assertEqual(_fmt(3600), '1h 0m')

    def test_one_hour_one_minute(self):
        self.assertEqual(_fmt(3661), '1h 1m')

    def test_two_hours_thirty_minutes(self):
        self.assertEqual(_fmt(9000), '2h 30m')


# count_by_type
class CountByTypeTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pass')

    def test_empty_queryset_all_zero(self):
        events = Event.objects.none()
        counts = count_by_type(events)
        self.assertTrue(all(v == 0 for v in counts.values()))

    def test_counts_correct_type(self):
        make_event(self.user, event_type=Event.EventType.DEADLINE)
        make_event(self.user, event_type=Event.EventType.DEADLINE)
        make_event(self.user, event_type=Event.EventType.EXAM)
        events = get_user_events(self.user)
        counts = count_by_type(events)
        self.assertEqual(counts['Deadline'], 2)
        self.assertEqual(counts['Exam'], 1)
        self.assertEqual(counts['Other'], 0)

    def test_all_types_present_as_keys(self):
        events = Event.objects.none()
        counts = count_by_type(events)
        for _, label in Event.EventType.choices:
            self.assertIn(label, counts)


# events_last_n_weeks
class EventsLastNWeeksTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pass')

    def test_returns_n_items(self):
        events = Event.objects.none()
        result = events_last_n_weeks(events, n=4)
        self.assertEqual(len(result), 4)

    def test_each_item_has_label_and_count(self):
        events = Event.objects.none()
        for item in events_last_n_weeks(events, n=3):
            self.assertIn('label', item)
            self.assertIn('count', item)

    def test_event_this_week_in_last_entry(self):
        # Event from 2 days ago → should be in the last week bucket
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='Recent',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=2) + timedelta(hours=1),
            allow_conflict=True,
        )
        events = get_user_events(self.user)
        result = events_last_n_weeks(events, n=4)
        self.assertEqual(result[-1]['count'], 1)

    def test_event_outside_range_not_counted(self):
        # Event 10 weeks ago → not in last 8 weeks
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='Old',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(weeks=10),
            end_datetime=now - timedelta(weeks=10) + timedelta(hours=1),
            allow_conflict=True,
        )
        events = get_user_events(self.user)
        result = events_last_n_weeks(events, n=8)
        self.assertEqual(sum(w['count'] for w in result), 0)


# events_last_n_months
class EventsLastNMonthsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pass')

    def test_returns_n_items(self):
        events = Event.objects.none()
        self.assertEqual(len(events_last_n_months(events, n=6)), 6)

    def test_event_this_month_in_last_entry(self):
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='This Month',
            event_type=Event.EventType.OTHER,
            start_datetime=now - timedelta(days=3),
            end_datetime=now - timedelta(days=3) + timedelta(hours=1),
            allow_conflict=True,
        )
        events = get_user_events(self.user)
        result = events_last_n_months(events, n=6)
        self.assertEqual(result[-1]['count'], 1)

    def test_each_item_has_label_and_count(self):
        events = Event.objects.none()
        for item in events_last_n_months(events, n=3):
            self.assertIn('label', item)
            self.assertIn('count', item)


# get_urgent_events
class GetUrgentEventsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pass')

    def _events(self):
        return get_user_events(self.user)

    def test_deadline_within_7_days_included(self):
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=48)
        self.assertEqual(get_urgent_events(self._events()).count(), 1)

    def test_exam_within_7_days_included(self):
        make_event(self.user, event_type=Event.EventType.EXAM, hours_from_now=24)
        self.assertEqual(get_urgent_events(self._events()).count(), 1)

    def test_deadline_after_7_days_excluded(self):
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=8 * 24)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_past_deadline_excluded(self):
        make_event(self.user, event_type=Event.EventType.DEADLINE, hours_from_now=-2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_class_type_excluded(self):
        make_event(self.user, event_type=Event.EventType.CLASS, hours_from_now=2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)

    def test_meeting_type_excluded(self):
        make_event(self.user, event_type=Event.EventType.MEETING, hours_from_now=2)
        self.assertEqual(get_urgent_events(self._events()).count(), 0)


# get_focus_stats
class GetFocusStatsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pass')

    def test_required_keys_present(self):
        stats = get_focus_stats(self.user)
        for key in ('focus_total', 'focus_avg', 'focus_sessions_count', 'focus_daily', 'focus_max_seconds'):
            self.assertIn(key, stats)

    def test_no_sessions_total_zero(self):
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 0)
        self.assertEqual(stats['focus_total'], '0m')

    def test_focus_daily_has_7_entries(self):
        stats = get_focus_stats(self.user)
        self.assertEqual(len(stats['focus_daily']), 7)

    def test_session_within_7_days_counted(self):
        make_focus_session(self.user, seconds=3600, days_ago=2)
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 1)
        self.assertEqual(stats['focus_total'], '1h 0m')

    def test_session_older_than_7_days_excluded(self):
        make_focus_session(self.user, seconds=3600, days_ago=8)
        stats = get_focus_stats(self.user)
        self.assertEqual(stats['focus_sessions_count'], 0)


# get_friend_focus_leaderboard
class GetFriendLeaderboardTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='me', password='pass')
        self.friend = User.objects.create_user(username='friend', password='pass')
        self.user.following.add(self.friend)

    def test_user_in_leaderboard(self):
        board = get_friend_focus_leaderboard(self.user)
        users = [e['user'] for e in board]
        self.assertIn(self.user, users)

    def test_followed_user_in_leaderboard(self):
        board = get_friend_focus_leaderboard(self.user)
        users = [e['user'] for e in board]
        self.assertIn(self.friend, users)

    def test_sorted_descending_by_seconds(self):
        make_focus_session(self.friend, seconds=7200)
        board = get_friend_focus_leaderboard(self.user)
        seconds = [e['seconds'] for e in board]
        self.assertEqual(seconds, sorted(seconds, reverse=True))

    def test_is_self_flag_correct(self):
        board = get_friend_focus_leaderboard(self.user)
        for entry in board:
            if entry['user'] == self.user:
                self.assertTrue(entry['is_self'])
            else:
                self.assertFalse(entry['is_self'])


# statistics_view
class StatisticsViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='pass')
        self.url = reverse('statistics')

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_authenticated_returns_200(self):
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_has_required_keys(self):
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        for key in ('total_events', 'type_counts', 'weekly_data', 'monthly_data',
                    'urgent_events', 'focus_total', 'focus_daily', 'friend_leaderboard'):
            self.assertIn(key, response.context)

    def test_total_events_reflects_user_events(self):
        make_event(self.user)
        make_event(self.user)
        self.client.login(username='u', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_events'], 2)


# statistics_view (lines 148-149) — not bound to a URL, called via RequestFactory
class StatisticsViewDirectTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='direct_user', password='pass')

    def test_statistics_view_calls_build_context_and_render(self):
        request = self.factory.get('/statistics/')
        request.user = self.user
        with patch('timeout.views.statistics.render', return_value=HttpResponse()) as mock_render:
            response = statistics_view(request)
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
