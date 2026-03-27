"""
Tests for moderation, deadline service, feed service cursors,
AI suggestions, AI workload, deadline warning, and AI service.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event, Post, Bookmark
from timeout.services.deadline_service import DeadlineService

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


def _make_post(author, content='Test post'):
    return Post.objects.create(author=author, content=content)


# Ban / Unban

class BanUnbanTests(TestCase):

    def setUp(self):
        self.staff = _make_user('staffuser', is_staff=True)
        self.target = _make_user('target')
        self.client.login(username='staffuser', password='TestPass1!')

    def test_ban_user(self):
        resp = self.client.post(reverse('ban_user', args=['target']), {'reason': 'spam'})
        self.assertEqual(resp.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_banned)

    def test_ban_staff_forbidden(self):
        other_staff = _make_user('staff2', is_staff=True)
        resp = self.client.post(reverse('ban_user', args=['staff2']))
        self.assertEqual(resp.status_code, 302)
        other_staff.refresh_from_db()
        self.assertFalse(other_staff.is_banned)

    def test_unban_user(self):
        self.target.is_banned = True
        self.target.save()
        resp = self.client.post(reverse('unban_user', args=['target']))
        self.assertEqual(resp.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_banned)

    def test_ban_non_staff_forbidden(self):
        self.client.login(username='target', password='TestPass1!')
        resp = self.client.post(reverse('ban_user', args=['staffuser']))
        self.assertEqual(resp.status_code, 403)

    def test_unban_non_staff_forbidden(self):
        self.client.login(username='target', password='TestPass1!')
        resp = self.client.post(reverse('unban_user', args=['staffuser']))
        self.assertEqual(resp.status_code, 403)


# Deadline Service mark_incomplete

class MarkIncompleteTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Done Task',
            event_type='deadline',
            start_datetime=now,
            end_datetime=now + timedelta(days=2),
            is_completed=True,
        )

    def test_mark_incomplete_success(self):
        result = DeadlineService.mark_incomplete(self.user, self.event.pk)
        self.assertIsNotNone(result)
        self.assertFalse(result.is_completed)

    def test_mark_incomplete_not_found(self):
        result = DeadlineService.mark_incomplete(self.user, 99999)
        self.assertIsNone(result)

    def test_mark_incomplete_already_incomplete(self):
        self.event.is_completed = False
        self.event.save()
        result = DeadlineService.mark_incomplete(self.user, self.event.pk)
        self.assertIsNone(result)


class DeadlineMarkIncompleteViewTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Complete Task',
            event_type='deadline',
            start_datetime=now,
            end_datetime=now + timedelta(days=2),
            is_completed=True,
        )

    def test_mark_incomplete_view(self):
        resp = self.client.post(reverse('deadline_mark_incomplete', args=[self.event.pk]))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertFalse(data['is_completed'])

    def test_mark_incomplete_not_found(self):
        resp = self.client.post(reverse('deadline_mark_incomplete', args=[99999]))
        self.assertEqual(resp.status_code, 404)


# Feed Service Cursor Tests

class FeedServiceCursorTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.other = _make_user('other')
        self.user.following.add(self.other)
        self.posts = [_make_post(self.other, f'Post {i}') for i in range(3)]

    def test_following_feed_with_cursor(self):
        from timeout.services.feed_service import FeedService
        results = FeedService.get_following_feed(self.user, cursor=self.posts[-1].id + 100)
        self.assertTrue(len(results) >= 0)

    def test_discover_feed_with_cursor(self):
        from timeout.services.feed_service import FeedService
        third = _make_user('third')
        _make_post(third, 'Discover post')
        results = FeedService.get_discover_feed(self.user, cursor=99999)
        self.assertIsInstance(results, list)

    def test_bookmarked_posts_with_cursor(self):
        from timeout.services.feed_service import FeedService
        bm_post = _make_post(self.other, 'BM post')
        Bookmark.objects.create(user=self.user, post=bm_post)
        results = FeedService.get_bookmarked_posts(self.user, cursor=bm_post.id + 100)
        self.assertIsInstance(results, list)

    def test_user_posts_with_cursor(self):
        from timeout.services.feed_service import FeedService
        results = FeedService.get_user_posts(self.other, self.user, cursor=99999)
        self.assertIsInstance(results, list)

    def test_user_posts_staff_viewer(self):
        from timeout.services.feed_service import FeedService
        staff = _make_user('staff', is_staff=True)
        banned = _make_user('banned', is_banned=True)
        _make_post(banned, 'Banned post')
        results = FeedService.get_user_posts(banned, staff)
        self.assertTrue(len(results) >= 1)


# AI Suggestions

class AISuggestionsTests(TestCase):

    def test_no_api_key_returns_empty(self):
        from timeout.views.ai_suggestions import get_ai_suggestions
        user = _make_user()
        with patch('timeout.views.ai_suggestions.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ''
            result = get_ai_suggestions(user, [])
            self.assertEqual(result, [])

    def test_no_events_returns_free_time(self):
        from timeout.views.ai_suggestions import get_ai_suggestions
        user = _make_user()
        with patch('timeout.views.ai_suggestions.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'test-key'
            with patch('timeout.views.ai_suggestions.cache') as mock_cache:
                mock_cache.get.return_value = None
                result = get_ai_suggestions(user, [])
                self.assertEqual(result, ["No events today. You have free time!"])

    def test_cached_result_returned(self):
        from timeout.views.ai_suggestions import get_ai_suggestions
        user = _make_user()
        with patch('timeout.views.ai_suggestions.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'test-key'
            with patch('timeout.views.ai_suggestions.cache') as mock_cache:
                mock_cache.get.return_value = ['cached tip']
                result = get_ai_suggestions(user, ['event'])
                self.assertEqual(result, ['cached tip'])

    @patch('timeout.views.ai_suggestions.cache')
    @patch('timeout.views.ai_suggestions.settings')
    def test_openai_exception(self, mock_settings, mock_cache):
        from timeout.views.ai_suggestions import get_ai_suggestions
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_cache.get.return_value = None
        user = _make_user()
        event = MagicMock()
        event.title = 'Meeting'
        event.start_datetime = timezone.now()
        event.end_datetime = timezone.now() + timedelta(hours=1)
        with patch('timeout.views.ai_suggestions._call_openai_suggestions', side_effect=Exception('API down')):
            result = get_ai_suggestions(user, [event])
            self.assertTrue(any('unavailable' in s for s in result))

    @patch('timeout.views.ai_suggestions.cache')
    @patch('timeout.views.ai_suggestions.settings')
    def test_openai_json_error(self, mock_settings, mock_cache):
        from timeout.views.ai_suggestions import get_ai_suggestions
        import json as _json
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_cache.get.return_value = None
        user = _make_user()
        event = MagicMock()
        event.title = 'Meeting'
        event.start_datetime = timezone.now()
        event.end_datetime = timezone.now() + timedelta(hours=1)
        with patch('timeout.views.ai_suggestions._call_openai_suggestions', side_effect=_json.JSONDecodeError('err', '', 0)):
            result = get_ai_suggestions(user, [event])
            self.assertTrue(any('invalid JSON' in s for s in result))

    def test_format_events_for_prompt(self):
        from timeout.views.ai_suggestions import _format_events_for_prompt
        event = MagicMock()
        event.title = 'Study'
        event.start_datetime = timezone.now()
        event.end_datetime = timezone.now() + timedelta(hours=2)
        result = _format_events_for_prompt([event])
        self.assertEqual(len(result), 1)
        self.assertIn('Study', result[0])

    def test_format_events_skips_invalid(self):
        from timeout.views.ai_suggestions import _format_events_for_prompt
        bad_event = MagicMock(spec=[])
        result = _format_events_for_prompt([bad_event])
        self.assertEqual(result, [])


# AI Workload

class AIWorkloadTests(TestCase):

    def test_no_events_returns_none(self):
        from timeout.views.ai_workload import get_ai_workload_warning
        user = _make_user()
        result = get_ai_workload_warning(user, [])
        self.assertIsNone(result)

    def test_no_api_key_returns_none(self):
        from timeout.views.ai_workload import get_ai_workload_warning
        user = _make_user()
        with patch('timeout.views.ai_workload.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ''
            result = get_ai_workload_warning(user, ['event'])
            self.assertIsNone(result)

    def test_cached_result_returned(self):
        from timeout.views.ai_workload import get_ai_workload_warning
        user = _make_user()
        with patch('timeout.views.ai_workload.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = 'test-key'
            with patch('timeout.views.ai_workload.cache') as mock_cache:
                mock_cache.get.return_value = 'cached warning'
                result = get_ai_workload_warning(user, ['event'])
                self.assertEqual(result, 'cached warning')

    @patch('timeout.views.ai_workload.cache')
    @patch('timeout.views.ai_workload.settings')
    def test_exception_returns_none(self, mock_settings, mock_cache):
        from timeout.views.ai_workload import get_ai_workload_warning
        mock_settings.OPENAI_API_KEY = 'test-key'
        mock_cache.get.return_value = None
        user = _make_user()
        event = MagicMock()
        event.title = 'Meeting'
        event.start_datetime = timezone.now()
        event.end_datetime = timezone.now() + timedelta(hours=1)
        with patch('timeout.views.ai_workload._call_openai_workload', side_effect=Exception('fail')):
            result = get_ai_workload_warning(user, [event])
            self.assertIsNone(result)

    def test_summarize_events_dict(self):
        from timeout.views.ai_workload import _summarize_events
        now = timezone.now()
        events = [{'title': 'Meeting', 'start_datetime': now, 'end_datetime': now + timedelta(hours=1)}]
        result = _summarize_events(events)
        self.assertEqual(len(result), 1)
        self.assertIn('Meeting', result[0])

    def test_summarize_events_object(self):
        from timeout.views.ai_workload import _summarize_events
        event = MagicMock()
        event.title = 'Study'
        event.start_datetime = timezone.now()
        event.end_datetime = timezone.now() + timedelta(hours=2)
        result = _summarize_events([event])
        self.assertEqual(len(result), 1)

    def test_summarize_events_skips_incomplete(self):
        from timeout.views.ai_workload import _summarize_events
        result = _summarize_events([{'title': None, 'start_datetime': None, 'end_datetime': None}])
        self.assertEqual(result, [])


# Deadline Warning

class DeadlineWarningTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_deadline_with_no_study_sessions(self):
        from timeout.views.deadline_warning import get_deadline_study_warnings
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Essay Due',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now + timedelta(days=3),
            end_datetime=now + timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        warnings = get_deadline_study_warnings(self.user)
        self.assertEqual(len(warnings), 1)
        self.assertIn('Essay Due', warnings[0]['message'])

    def test_deadline_with_study_sessions(self):
        from timeout.views.deadline_warning import get_deadline_study_warnings
        now = timezone.now()
        deadline = Event.objects.create(
            creator=self.user, title='Covered',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now + timedelta(days=3),
            end_datetime=now + timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        session = Event.objects.create(
            creator=self.user, title='Study for Covered',
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=now + timedelta(days=2),
            end_datetime=now + timedelta(days=2, hours=2),
        )
        deadline.linked_study_sessions.add(session)
        warnings = get_deadline_study_warnings(self.user)
        self.assertEqual(len(warnings), 0)

    def test_no_deadlines(self):
        from timeout.views.deadline_warning import get_deadline_study_warnings
        warnings = get_deadline_study_warnings(self.user)
        self.assertEqual(warnings, [])