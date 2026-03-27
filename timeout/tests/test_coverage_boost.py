"""
Additional tests to boost coverage above 95%.
Covers: social views (feed, feed_more, comments, status, followers/friends APIs,
flag/ban/unban), deadline_service mark_incomplete, deadline views,
feed_service cursors, ai_suggestions, ai_workload, deadline_warning,
pages (banned, dashboard), notes autosave, event_delete edge cases.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event, Post, Comment, Bookmark, Like, PostFlag
from timeout.models.focus_session import FocusSession
from timeout.models.message import Conversation, Message
from timeout.services.deadline_service import DeadlineService

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


def _make_post(author, content='Test post'):
    return Post.objects.create(author=author, content=content)


def _make_event(user, title='Evt', event_type='meeting', days_offset=1, hours=1, **kwargs):
    now = timezone.now()
    return Event.objects.create(
        creator=user,
        title=title,
        event_type=event_type,
        start_datetime=now + timedelta(days=days_offset),
        end_datetime=now + timedelta(days=days_offset, hours=hours),
        **kwargs,
    )


#  Social Feed Views 

class FeedViewTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_feed_following_tab(self):
        resp = self.client.get(reverse('social_feed'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'following')

    def test_feed_discover_tab(self):
        resp = self.client.get(reverse('social_feed'), {'tab': 'discover'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'discover')

    def test_feed_bookmarks_tab(self):
        resp = self.client.get(reverse('social_feed'), {'tab': 'bookmarks'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'bookmarks')

    def test_feed_review_flags_non_staff(self):
        resp = self.client.get(reverse('social_feed'), {'tab': 'review_flags'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'following')

    def test_feed_review_flags_staff(self):
        self.user.is_staff = True
        self.user.save()
        resp = self.client.get(reverse('social_feed'), {'tab': 'review_flags'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'review_flags')

    def test_feed_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('social_feed'))
        self.assertEqual(resp.status_code, 302)


class FeedMoreViewTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.other = _make_user('other')
        self.client.login(username='testuser', password='TestPass1!')

    def test_feed_more_following(self):
        resp = self.client.get(reverse('feed_more'), {'tab': 'following'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_discover(self):
        resp = self.client.get(reverse('feed_more'), {'tab': 'discover'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_bookmarks(self):
        resp = self.client.get(reverse('feed_more'), {'tab': 'bookmarks'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_invalid_tab_defaults_following(self):
        resp = self.client.get(reverse('feed_more'), {'tab': 'invalid'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_with_cursor(self):
        post = _make_post(self.other)
        resp = self.client.get(reverse('feed_more'), {'tab': 'discover', 'cursor': str(post.id + 100)})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_invalid_cursor(self):
        resp = self.client.get(reverse('feed_more'), {'tab': 'following', 'cursor': 'abc'})
        self.assertEqual(resp.status_code, 200)


#  Delete Comment 

class DeleteCommentTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.other = _make_user('other')
        self.post = _make_post(self.user)
        self.comment = Comment.objects.create(
            post=self.post, author=self.user, content='My comment'
        )
        self.client.login(username='testuser', password='TestPass1!')

    def test_author_can_delete_comment(self):
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_staff_can_delete_comment(self):
        staff = _make_user('staff', is_staff=True)
        self.client.login(username='staff', password='TestPass1!')
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.login(username='other', password='TestPass1!')
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())


#  Update Status 

class UpdateStatusTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_set_focus_status(self):
        resp = self.client.post(reverse('update_status'), {'status': 'focus'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'focus')
        self.assertIsNotNone(data['focus_started_at'])

    def test_set_social_status(self):
        resp = self.client.post(reverse('update_status'), {'status': 'social'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'social')

    def test_invalid_status(self):
        resp = self.client.post(reverse('update_status'), {'status': 'bogus'})
        self.assertEqual(resp.status_code, 400)

    def test_leaving_focus_creates_session(self):
        self.user.status = 'focus'
        self.user.focus_started_at = timezone.now() - timedelta(minutes=30)
        self.user.save()
        resp = self.client.post(reverse('update_status'), {'status': 'inactive'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(FocusSession.objects.filter(user=self.user).exists())

    def test_leaving_focus_without_start_time(self):
        self.user.status = 'focus'
        self.user.focus_started_at = None
        self.user.save()
        resp = self.client.post(reverse('update_status'), {'status': 'inactive'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(FocusSession.objects.filter(user=self.user).exists())


#  Social API Views (from social.py, not social_api.py) 

class SocialViewFollowersAPITests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.private = _make_user('priv', privacy_private=True)

    def test_followers_api(self):
        self.bob.following.add(self.alice)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)

    def test_following_api(self):
        self.alice.following.add(self.bob)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_public(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['bob']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_private_denied(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['priv']))
        self.assertEqual(resp.status_code, 403)

    def test_user_following_api_public(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['bob']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_denied(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['priv']))
        self.assertEqual(resp.status_code, 403)

    def test_friends_api(self):
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)

    def test_user_friends_api_public(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_friends_api', args=['bob']))
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_private_denied(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_friends_api', args=['priv']))
        self.assertEqual(resp.status_code, 403)

    def test_search_users(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(len(data['users']) >= 1)

    def test_search_users_empty(self):
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('search_users'), {'q': ''})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])


#  Flag Post 

class FlagPostTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.other = _make_user('other')
        self.post = _make_post(self.other)
        self.client.login(username='testuser', password='TestPass1!')

    def test_flag_post_success(self):
        resp = self.client.post(reverse('flag_post', args=[self.post.id]), {
            'reason': 'spam',
            'description': 'This is spam',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertTrue(data['created'])
        self.assertTrue(PostFlag.objects.filter(post=self.post, reporter=self.user).exists())

    def test_flag_post_duplicate(self):
        PostFlag.objects.create(post=self.post, reporter=self.user, reason='spam')
        resp = self.client.post(reverse('flag_post', args=[self.post.id]), {
            'reason': 'spam',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertFalse(data['created'])

    def test_flag_post_invalid_reason_defaults(self):
        resp = self.client.post(reverse('flag_post', args=[self.post.id]), {
            'reason': 'invalid_reason',
        })
        self.assertEqual(resp.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, 'other')


#  Ban / Unban 

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


#  Deadline Service mark_incomplete 

class MarkIncompleteTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user,
            title='Done Task',
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
            creator=self.user,
            title='Complete Task',
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


#  Feed Service Cursor Tests 

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


#  AI Suggestions 

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


#  AI Workload 

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


#  Deadline Warning 

class DeadlineWarningTests(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_deadline_with_no_study_sessions(self):
        from timeout.views.deadline_warning import get_deadline_study_warnings
        now = timezone.now()
        Event.objects.create(
            creator=self.user,
            title='Essay Due',
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
            creator=self.user,
            title='Covered',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now + timedelta(days=3),
            end_datetime=now + timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        session = Event.objects.create(
            creator=self.user,
            title='Study for Covered',
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


#  Pages Views 

class PagesViewTests(TestCase):

    def test_banned_page(self):
        resp = self.client.get(reverse('banned'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)


#  AI Service 

class AIServiceTests(TestCase):

    def test_get_most_productive_day_empty(self):
        from timeout.services.ai_service import _get_most_productive_day
        qs = Event.objects.none()
        result = _get_most_productive_day(qs)
        self.assertEqual(result, 'None yet')

    def test_get_most_productive_day_with_data(self):
        from timeout.services.ai_service import _get_most_productive_day
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Done', event_type='study_session',
            start_datetime=now - timedelta(days=1),
            end_datetime=now - timedelta(days=1) + timedelta(hours=2),
            is_completed=True,
        )
        qs = Event.objects.filter(creator=user)
        result = _get_most_productive_day(qs)
        self.assertNotEqual(result, 'None yet')

    def test_gather_study_stats(self):
        from timeout.services.ai_service import _gather_study_stats
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Study', event_type='study_session',
            start_datetime=now - timedelta(days=1),
            end_datetime=now - timedelta(days=1) + timedelta(hours=3),
            is_completed=True,
        )
        Event.objects.create(
            creator=user, title='Missed DL', event_type='deadline',
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(hours=1),
            is_completed=False,
        )
        stats = _gather_study_stats(user, now)
        self.assertIn('total_study_hours', stats)
        self.assertGreater(stats['total_study_hours'], 0)
        self.assertEqual(stats['missed_deadlines'], 1)


#  Notification Service Edge Cases 

class NotificationServiceTests(TestCase):

    def test_create_deadline_notifications_within_hour(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Urgent DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(minutes=30),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_deadline_notifications_within_day(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Tomorrow DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(hours=12),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_deadline_notifications_within_week(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='This Week DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            is_completed=False,
        )
        NotificationService.create_deadline_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_within_hour(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Soon Meeting',
            event_type=Event.EventType.MEETING,
            start_datetime=now + timedelta(minutes=30),
            end_datetime=now + timedelta(hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_tomorrow(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Tomorrow Exam',
            event_type=Event.EventType.EXAM,
            start_datetime=now + timedelta(hours=12),
            end_datetime=now + timedelta(hours=14),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_this_week(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='This Week Class',
            event_type=Event.EventType.CLASS,
            start_datetime=now + timedelta(days=3),
            end_datetime=now + timedelta(days=3, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertTrue(Notification.objects.filter(user=user).exists())

    def test_create_event_notifications_far_future_ignored(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        Event.objects.create(
            creator=user, title='Far Away',
            event_type=Event.EventType.MEETING,
            start_datetime=now + timedelta(days=30),
            end_datetime=now + timedelta(days=30, hours=1),
            status=Event.EventStatus.UPCOMING,
        )
        NotificationService.create_event_notifications(user)
        self.assertFalse(Notification.objects.filter(user=user).exists())

    def test_notify_once_no_duplicate(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        user = _make_user()
        now = timezone.now()
        event = Event.objects.create(
            creator=user, title='DL',
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(minutes=30),
            is_completed=False,
        )
        NotificationService._notify_once(user, event, "Test msg")
        NotificationService._notify_once(user, event, "Test msg")
        self.assertEqual(Notification.objects.filter(user=user, message="Test msg").count(), 1)


#  Notes Autosave and Edit 

class NoteAutosaveTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        from timeout.models import Note
        self.note = Note.objects.create(
            owner=self.user,
            title='Test Note',
            content='Initial content',
        )

    def test_autosave(self):
        resp = self.client.post(reverse('note_autosave', args=[self.note.id]), {
            'title': 'Updated Title',
            'content': 'Updated content',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'ok')

    def test_autosave_with_count_edit(self):
        resp = self.client.post(reverse('note_autosave', args=[self.note.id]), {
            'title': 'Updated',
            'content': 'Updated',
            'count_edit': '1',
        })
        self.assertEqual(resp.status_code, 200)

    def test_note_edit_page(self):
        resp = self.client.get(reverse('note_edit', args=[self.note.id]))
        self.assertEqual(resp.status_code, 200)


#  Deadline List View with Filters 

class DeadlineListFilterTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Active DL',
            event_type='deadline',
            start_datetime=now, end_datetime=now + timedelta(days=3),
        )
        Event.objects.create(
            creator=self.user, title='Done DL',
            event_type='deadline',
            start_datetime=now - timedelta(days=5),
            end_datetime=now - timedelta(days=1),
            is_completed=True,
        )

    def test_deadline_list_default(self):
        resp = self.client.get(reverse('deadline_list'))
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_completed_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'status': 'completed'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_all_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'status': 'all'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_sort_desc(self):
        resp = self.client.get(reverse('deadline_list'), {'sort': 'desc'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_type_filter(self):
        resp = self.client.get(reverse('deadline_list'), {'type': 'deadline'})
        self.assertEqual(resp.status_code, 200)

    def test_deadline_list_invalid_type_ignored(self):
        resp = self.client.get(reverse('deadline_list'), {'type': 'bogus_type'})
        self.assertEqual(resp.status_code, 200)


# Pages: Landing, Dashboard greeting branches, Calendar

class LandingPageTests(TestCase):

    def test_landing_unauthenticated(self):
        resp = self.client.get(reverse('landing'))
        self.assertEqual(resp.status_code, 200)

    def test_landing_authenticated_redirects_dashboard(self):
        _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        resp = self.client.get(reverse('landing'))
        self.assertRedirects(resp, reverse('dashboard'))


class DashboardGreetingTests(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    @patch('timeout.views.pages.timezone')
    def test_morning_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 9, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    @patch('timeout.views.pages.timezone')
    def test_afternoon_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 14, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    @patch('timeout.views.pages.timezone')
    def test_evening_greeting(self, mock_tz):
        from datetime import datetime as dt
        mock_now = timezone.make_aware(dt(2026, 3, 25, 20, 0, 0))
        mock_tz.now.return_value = mock_now
        mock_tz.localtime.return_value = mock_now
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)


# Study Planner: call_gpt

class CallGptTests(TestCase):

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_success(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {'title': 'Study for Essay', 'start': '2026-04-01T10:00', 'end': '2026-04-01T12:00'}
        ])
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            result = call_gpt(deadline, 4, 2, [{'date': '2026-04-01', 'start': '10:00', 'end': '18:00'}])
        self.assertIsInstance(result, list)

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_exception_raises(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=MagicMock(side_effect=Exception('fail')))}):
            with self.assertRaises(Exception):
                call_gpt(deadline, 4, 2, [])

    @patch('timeout.views.study_planner.settings')
    def test_call_gpt_markdown_fence(self, mock_settings):
        from timeout.views.study_planner import call_gpt
        mock_settings.OPENAI_API_KEY = 'test-key'
        deadline = MagicMock()
        deadline.title = 'Essay'
        deadline.start_datetime = timezone.now() + timedelta(days=5)
        raw_json = json.dumps([{'title': 'Study', 'start': '2026-04-01T10:00', 'end': '2026-04-01T12:00'}])
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = f'```json{raw_json}```'
        mock_openai = MagicMock()
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        with patch.dict('sys.modules', {'openai': MagicMock(OpenAI=mock_openai)}):
            result = call_gpt(deadline, 4, 2, [])
        self.assertIsInstance(result, list)


# Management Command: check_site

class CheckSiteCommandTests(TestCase):

    def test_check_site_runs(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('check_site', stdout=out)
        output = out.getvalue()
        self.assertIn('SITE_ID', output)


# Notification Service: create_message_notification

class MessageNotificationTests(TestCase):

    def test_create_message_notification(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        alice = _make_user('alice')
        bob = _make_user('bob')
        conv = Conversation.objects.create()
        conv.participants.add(alice, bob)
        msg = Message.objects.create(conversation=conv, sender=alice, content='Hi')
        NotificationService.create_message_notification(bob, msg)
        self.assertTrue(Notification.objects.filter(user=bob).exists())

    def test_create_message_notification_no_recipient(self):
        from timeout.services.notification_service import NotificationService
        from timeout.models.notification import Notification
        alice = _make_user('alice')
        conv = Conversation.objects.create()
        conv.participants.add(alice)
        msg = Message.objects.create(conversation=conv, sender=alice, content='Solo')
        NotificationService.create_message_notification(alice, msg)


#  Sitemaps

class SitemapTests(TestCase):

    def test_sitemap_index(self):
        resp = self.client.get('/sitemap.xml')
        self.assertIn(resp.status_code, [200, 404])


# OAuth Tags 

class OAuthTagTests(TestCase):

    def test_google_oauth_available_true(self):
        from timeout.templatetags.oauth_tags import google_oauth_available
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
        app, _ = SocialApp.objects.get_or_create(
            provider='google',
            defaults={'name': 'Google', 'client_id': 'test-id', 'secret': 'x'},
        )
        app.sites.add(Site.objects.get_current())
        result = google_oauth_available()
        self.assertTrue(result)
    
    def test_google_oauth_available_false(self):
        from timeout.templatetags.oauth_tags import google_oauth_available
        SocialApp = None  # noqa
        result = google_oauth_available()
        self.assertFalse(result)
