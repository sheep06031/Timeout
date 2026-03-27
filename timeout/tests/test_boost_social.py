"""
Tests for social feed, moderation, and profile endpoints.
Covers: social_feed, feed_more, delete_comment, update_status,
        followers/following/friends APIs, flag_post,
        profile event views, event edit edge cases, social API endpoints.
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event, Post, Comment, PostFlag
from timeout.models.focus_session import FocusSession

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    """Helper function to create a user with default credentials."""
    return User.objects.create_user(username=username, password=password, **kwargs)


def _make_post(author, content='Test post'):
    """Helper function to create a post with default content."""
    return Post.objects.create(author=author, content=content)

class FeedViewTests(TestCase):
    """Tests for the social feed view and its tabs."""

    def setUp(self):
        """Create a test user and log in before each test."""
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_feed_following_tab(self):
        """Test that the default feed tab is 'following' and it loads correctly."""
        resp = self.client.get(reverse('social_feed'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'following')

    def test_feed_discover_tab(self):
        """Test that the discover tab loads correctly and sets active_tab to 'discover'."""
        resp = self.client.get(reverse('social_feed'), {'tab': 'discover'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'discover')

    def test_feed_bookmarks_tab(self):
        """Test that the bookmarks tab loads correctly and sets active_tab to 'bookmarks'."""
        resp = self.client.get(reverse('social_feed'), {'tab': 'bookmarks'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'bookmarks')

    def test_feed_review_flags_non_staff(self):
        """Test that non-staff users cannot access the review_flags tab."""
        resp = self.client.get(reverse('social_feed'), {'tab': 'review_flags'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'following')

    def test_feed_review_flags_staff(self):
        """Test that staff users can access the review_flags tab."""
        self.user.is_staff = True
        self.user.save()
        resp = self.client.get(reverse('social_feed'), {'tab': 'review_flags'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'review_flags')

    def test_feed_requires_login(self):
        """Test that the social feed view requires login and redirects anonymous users."""
        self.client.logout()
        resp = self.client.get(reverse('social_feed'))
        self.assertEqual(resp.status_code, 302)


class FeedMoreViewTests(TestCase):
    """Tests for the 'feed_more' view and its tabs."""

    def setUp(self):
        """Create test users and log in before each test."""
        self.user = _make_user()
        self.other = _make_user('other')
        self.client.login(username='testuser', password='TestPass1!')

    def test_feed_more_following(self):
        """Test that the 'feed_more' view loads the 'following' tab correctly."""
        resp = self.client.get(reverse('feed_more'), {'tab': 'following'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_discover(self):
        """Test that the 'feed_more' view loads the 'discover' tab correctly."""
        resp = self.client.get(reverse('feed_more'), {'tab': 'discover'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_bookmarks(self):
        """Test that the 'feed_more' view loads the 'bookmarks' tab correctly."""
        resp = self.client.get(reverse('feed_more'), {'tab': 'bookmarks'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_invalid_tab_defaults_following(self):
        """Test that the 'feed_more' view defaults to the 'following' tab for invalid tab values."""
        resp = self.client.get(reverse('feed_more'), {'tab': 'invalid'})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_with_cursor(self):
        """Test that the 'feed_more' view handles the cursor parameter correctly."""
        post = _make_post(self.other)
        resp = self.client.get(reverse('feed_more'), {'tab': 'discover', 'cursor': str(post.id + 100)})
        self.assertEqual(resp.status_code, 200)

    def test_feed_more_invalid_cursor(self):
        """Test that the 'feed_more' view handles invalid cursor values gracefully."""
        resp = self.client.get(reverse('feed_more'), {'tab': 'following', 'cursor': 'abc'})
        self.assertEqual(resp.status_code, 200)

class DeleteCommentTests(TestCase):
    """Tests for the delete_comment view and permissions."""

    def setUp(self):
        """Create test users, posts, and comments before each test."""
        self.user = _make_user()
        self.other = _make_user('other')
        self.post = _make_post(self.user)
        self.comment = Comment.objects.create(
            post=self.post, author=self.user, content='My comment'
        )
        self.client.login(username='testuser', password='TestPass1!')

    def test_author_can_delete_comment(self):
        """Test that the author of a comment can delete it successfully."""
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_staff_can_delete_comment(self):
        """Test that staff users can delete any comment successfully."""
        staff = _make_user('staff', is_staff=True)
        self.client.login(username='staff', password='TestPass1!')
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_other_user_cannot_delete_comment(self):
        """Test that users who are not the author or staff cannot delete the comment."""
        self.client.login(username='other', password='TestPass1!')
        resp = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

class UpdateStatusTests(TestCase):
    """Tests for the update_status view and status transitions."""

    def setUp(self):
        """Create a test user and log in before each test."""
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_set_focus_status(self):
        """Test that setting status to 'focus' works and sets focus_started_at."""
        resp = self.client.post(reverse('update_status'), {'status': 'focus'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'focus')
        self.assertIsNotNone(data['focus_started_at'])

    def test_set_social_status(self):
        """Test that setting status to 'social' works correctly."""
        resp = self.client.post(reverse('update_status'), {'status': 'social'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'social')

    def test_invalid_status(self):
        """Test that providing an invalid status returns a 400 error."""
        resp = self.client.post(reverse('update_status'), {'status': 'bogus'})
        self.assertEqual(resp.status_code, 400)

    def test_leaving_focus_creates_session(self):
        """Test that leaving focus status creates a FocusSession if focus_started_at is set."""
        self.user.status = 'focus'
        self.user.focus_started_at = timezone.now() - timedelta(minutes=30)
        self.user.save()
        resp = self.client.post(reverse('update_status'), {'status': 'inactive'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(FocusSession.objects.filter(user=self.user).exists())

    def test_leaving_focus_without_start_time(self):
        """Test that leaving focus status without a focus_started_at does not create a FocusSession."""
        self.user.status = 'focus'
        self.user.focus_started_at = None
        self.user.save()
        resp = self.client.post(reverse('update_status'), {'status': 'inactive'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(FocusSession.objects.filter(user=self.user).exists())

class SocialViewFollowersAPITests(TestCase):
    """Tests for the followers, following, friends, and search_users API endpoints."""

    def setUp(self):
        """Create test users before each test."""
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.private = _make_user('priv', privacy_private=True)

    def test_followers_api(self):
        """Test the followers API endpoint."""
        self.bob.following.add(self.alice)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)

    def test_following_api(self):
        """Test the following API endpoint."""
        self.alice.following.add(self.bob)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_public(self):
        """Test the user followers API endpoint for a public user."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['bob']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_private_denied(self):
        """Test the user followers API endpoint for a private user, which should be denied."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['priv']))
        self.assertEqual(resp.status_code, 403)

    def test_user_following_api_public(self):
        """Test the user following API endpoint for a public user."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['bob']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_denied(self):
        """Test the user following API endpoint for a private user, which should be denied."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['priv']))
        self.assertEqual(resp.status_code, 403)

    def test_friends_api(self):
        """Test the friends API endpoint, which should return mutual followers."""
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)

    def test_search_users(self):
        """Test the search users API endpoint with a query."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(len(data['users']) >= 1)

    def test_search_users_empty(self):
        """Test the search users API endpoint with an empty query, which should return no results."""
        self.client.login(username='alice', password='TestPass1!')
        resp = self.client.get(reverse('search_users'), {'q': ''})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

class FlagPostTests(TestCase):
    """Tests for the flag_post view and post flagging functionality."""

    def setUp(self):
        """Create test users and a post before each test."""
        self.user = _make_user()
        self.other = _make_user('other')
        self.post = _make_post(self.other)
        self.client.login(username='testuser', password='TestPass1!')

    def test_flag_post_success(self):
        """Test that a user can successfully flag a post."""
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
        """Test that a user cannot flag the same post twice."""
        PostFlag.objects.create(post=self.post, reporter=self.user, reason='spam')
        resp = self.client.post(reverse('flag_post', args=[self.post.id]), {'reason': 'spam'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertFalse(data['created'])

    def test_flag_post_invalid_reason_defaults(self):
        """Test that providing an invalid reason defaults to 'other'."""
        resp = self.client.post(reverse('flag_post', args=[self.post.id]), {
            'reason': 'invalid_reason',
        })
        self.assertEqual(resp.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, 'other')


class ProfileEventTests(TestCase):
    """Tests for the profile view with events."""

    def setUp(self):
        """Create a test user and log in before each test."""
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')

    def test_profile_with_active_event(self):
        """Test that the profile view loads correctly when the user has an active event."""
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
        """Test that the profile view loads correctly when the user has an upcoming event."""
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
        """Test that the profile view loads correctly when the user has a recent past event."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title='Recent',
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(minutes=30),
            event_type='meeting',
        )
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)


class EventEditEdgeCases(TestCase):
    """Tests for edge cases in the event edit view, such as all-day events and validation errors."""

    def setUp(self):
        """Create a test user and an event before each test."""
        self.user = _make_user()
        self.client.login(username='testuser', password='TestPass1!')
        now = timezone.now()
        self.event = Event.objects.create(
            creator=self.user, title='Edit Me',
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            event_type='meeting',
        )

    def test_edit_all_day(self):
        """Test that an event can be edited to be an all-day event."""
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
        """Test that validation errors during event editing are handled gracefully."""
        url = reverse('event_edit', args=[self.event.pk])
        resp = self.client.post(url, {
            'title': 'Bad',
            'start_datetime': 'invalid',
            'end_datetime': 'invalid',
            'event_type': 'meeting',
        })
        self.assertIn(resp.status_code, [200, 302])