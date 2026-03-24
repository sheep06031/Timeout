"""
Miscellaneous coverage tests for remaining uncovered code paths.

Covers:
  - Management commands: check_notifications, init_site
  - EmailService (SendGrid, mocked)
  - Event model properties: is_past, is_ongoing, is_upcoming, mark_completed,
    __str__, save (public post creation), delete (linked post deletion)
  - FollowRequest model __str__
  - User.follower_count property
  - NoteAdmin: title_preview
  - PostFlagAdmin: post_preview
  - PostAdmin: content_preview, like_count, comment_count
  - Signals: on_social_account_linked
  - Social views: user_profile (own), search_users (empty query),
    followers_api, following_api, friends_api,
    user_followers_api / user_following_api for private accounts
"""

import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch, MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from timeout.admin.note_admin import NoteAdmin
from timeout.admin.social_admin import PostFlagAdmin, PostAdmin, CommentAdmin, LikeAdmin, BookmarkAdmin
from timeout.models import (
    Event, Post, Note, FollowRequest, PostFlag, User as _UserRef,
    Comment, Like, Bookmark,
)
from timeout.services.email_service import EmailService

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# ─── Management Commands ──────────────────────────────────────────────


class CheckNotificationsCommandTests(TestCase):
    """Tests for the check_notifications management command."""

    def setUp(self):
        self.user = _make_user()

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_calls_services_for_each_user(self, mock_svc):
        """The command should call both notification methods for every user."""
        out = StringIO()
        call_command('check_notifications', stdout=out)

        mock_svc.create_deadline_notifications.assert_called_once_with(self.user)
        mock_svc.create_event_notifications.assert_called_once_with(self.user)
        self.assertIn('Notifications checked', out.getvalue())

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_multiple_users(self, mock_svc):
        """Ensure both methods are called once per user."""
        user2 = _make_user('user2')
        out = StringIO()
        call_command('check_notifications', stdout=out)

        self.assertEqual(mock_svc.create_deadline_notifications.call_count, 2)
        self.assertEqual(mock_svc.create_event_notifications.call_count, 2)

    @patch('timeout.management.commands.check_notifications.NotificationService')
    def test_check_notifications_no_users(self, mock_svc):
        """When there are no users, nothing should be called."""
        User.objects.all().delete()
        out = StringIO()
        call_command('check_notifications', stdout=out)

        mock_svc.create_deadline_notifications.assert_not_called()
        mock_svc.create_event_notifications.assert_not_called()


class InitSiteCommandTests(TestCase):
    """Tests for the init_site management command."""

    def test_init_site_creates_site(self):
        """init_site should create a Site with id=1."""
        Site.objects.all().delete()
        out = StringIO()
        call_command('init_site', stdout=out)

        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')
        self.assertEqual(site.name, 'Timeout Local')
        self.assertIn('Created Site', out.getvalue())

    def test_init_site_replaces_existing_site(self):
        """Running init_site when a Site already exists replaces it."""
        Site.objects.all().delete()
        Site.objects.create(id=1, domain='old.example.com', name='Old')

        out = StringIO()
        call_command('init_site', stdout=out)

        self.assertEqual(Site.objects.count(), 1)
        site = Site.objects.get(id=1)
        self.assertEqual(site.domain, '127.0.0.1:8000')

    def test_init_site_idempotent(self):
        """Running init_site twice should still result in a single Site."""
        Site.objects.all().delete()
        call_command('init_site', stdout=StringIO())
        call_command('init_site', stdout=StringIO())

        self.assertEqual(Site.objects.count(), 1)


# ─── EmailService ─────────────────────────────────────────────────────


class EmailServiceTests(TestCase):
    """Tests for EmailService.send_reset_code."""

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_success(self, mock_settings):
        """When SendGrid succeeds, return True."""
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'

        mock_sg_instance = MagicMock()
        mock_sg_client = MagicMock(return_value=mock_sg_instance)
        mock_mail_class = MagicMock()

        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=mock_mail_class),
        }):
            result = EmailService.send_reset_code('user@example.com', '123456')

        self.assertTrue(result)
        mock_sg_instance.send.assert_called_once()

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_failure(self, mock_settings):
        """When SendGrid raises an exception, return False."""
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'

        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception('API error')
        mock_sg_client = MagicMock(return_value=mock_sg_instance)
        mock_mail_class = MagicMock()

        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=mock_mail_class),
        }):
            result = EmailService.send_reset_code('user@example.com', '999999')

        self.assertFalse(result)

    @patch('timeout.services.email_service.settings')
    def test_send_reset_code_logs_on_failure(self, mock_settings):
        """Errors should be logged."""
        mock_settings.SENDGRID_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SENDGRID_API_KEY = 'SG.fake_key'

        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception('timeout')
        mock_sg_client = MagicMock(return_value=mock_sg_instance)

        with patch.dict('sys.modules', {
            'sendgrid': MagicMock(SendGridAPIClient=mock_sg_client),
            'sendgrid.helpers': MagicMock(),
            'sendgrid.helpers.mail': MagicMock(Mail=MagicMock()),
        }):
            with patch('timeout.services.email_service.logger') as mock_logger:
                EmailService.send_reset_code('user@example.com', '000000')
                mock_logger.error.assert_called_once()


# ─── Event Model Properties ───────────────────────────────────────────


class EventModelPropertyTests(TestCase):
    """Tests for Event model computed properties and methods."""

    def setUp(self):
        self.user = _make_user()
        self.now = timezone.now()

    def _make_event(self, **kwargs):
        defaults = {
            'creator': self.user,
            'title': 'Test Event',
            'event_type': Event.EventType.MEETING,
            'start_datetime': self.now - timedelta(hours=2),
            'end_datetime': self.now + timedelta(hours=2),
            'visibility': Event.Visibility.PRIVATE,
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    # ── is_past ──

    def test_is_past_true(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertTrue(event.is_past)

    def test_is_past_false_when_ongoing(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_past)

    def test_is_past_false_when_upcoming(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_past)

    # ── is_ongoing ──

    def test_is_ongoing_true(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertTrue(event.is_ongoing)

    def test_is_ongoing_false_when_past(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_ongoing)

    def test_is_ongoing_false_when_upcoming(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_ongoing)

    # ── is_upcoming ──

    def test_is_upcoming_true(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertTrue(event.is_upcoming)

    def test_is_upcoming_false_when_past(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(days=2),
            end_datetime=self.now - timedelta(days=1),
        )
        self.assertFalse(event.is_upcoming)

    def test_is_upcoming_false_when_ongoing(self):
        event = self._make_event(
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
        )
        self.assertFalse(event.is_upcoming)

    # ── __str__ ──

    def test_str(self):
        event = self._make_event(title='My Meeting')
        expected = f"My Meeting ({event.start_datetime.date()})"
        self.assertEqual(str(event), expected)

    # ── mark_completed ──

    def test_mark_completed(self):
        event = self._make_event(
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
        )
        self.assertFalse(event.is_completed)

        event.mark_completed()
        event.refresh_from_db()

        self.assertTrue(event.is_completed)
        self.assertIsNotNone(event.completed_at)
        self.assertIsNotNone(event.actual_duration_hours)
        self.assertGreaterEqual(event.actual_duration_hours, 0)

    # ── save creates post for PUBLIC events ──

    def test_save_public_event_creates_post(self):
        event = self._make_event(
            visibility=Event.Visibility.PUBLIC,
        )
        self.assertTrue(Post.objects.filter(event=event).exists())

    def test_save_public_event_updates_existing_post(self):
        event = self._make_event(
            visibility=Event.Visibility.PUBLIC,
        )
        post_count_before = Post.objects.filter(event=event).count()
        self.assertEqual(post_count_before, 1)

        # Update the event (re-save)
        event.title = 'Updated Title'
        event.save()

        # Still one post, but content updated
        self.assertEqual(Post.objects.filter(event=event).count(), 1)
        post = Post.objects.get(event=event)
        self.assertIn('Updated Title', post.content)

    def test_save_private_event_no_post(self):
        event = self._make_event(
            visibility=Event.Visibility.PRIVATE,
        )
        self.assertFalse(Post.objects.filter(event=event).exists())

    def test_save_private_event_deletes_existing_post(self):
        # Start as public to create a post
        event = self._make_event(
            visibility=Event.Visibility.PUBLIC,
        )
        self.assertTrue(Post.objects.filter(event=event).exists())

        # Switch to private
        event.visibility = Event.Visibility.PRIVATE
        event.save()
        self.assertFalse(Post.objects.filter(event=event).exists())

    # ── delete removes linked posts ──

    def test_delete_event_removes_linked_posts(self):
        event = self._make_event(
            visibility=Event.Visibility.PUBLIC,
        )
        self.assertTrue(Post.objects.filter(event=event).exists())
        event_pk = event.pk
        event.delete()
        self.assertFalse(Post.objects.filter(event_id=event_pk).exists())

    # ── Event types ──

    def test_event_type_exam(self):
        event = self._make_event(event_type=Event.EventType.EXAM)
        self.assertEqual(event.event_type, 'exam')

    def test_event_type_deadline(self):
        event = self._make_event(event_type=Event.EventType.DEADLINE)
        self.assertEqual(event.event_type, 'deadline')

    def test_event_type_class(self):
        event = self._make_event(event_type=Event.EventType.CLASS)
        self.assertEqual(event.event_type, 'class')

    def test_event_type_study_session(self):
        event = self._make_event(event_type=Event.EventType.STUDY_SESSION)
        self.assertEqual(event.event_type, 'study_session')

    def test_event_type_other(self):
        event = self._make_event(event_type=Event.EventType.OTHER)
        self.assertEqual(event.event_type, 'other')


# ─── FollowRequest Model ─────────────────────────────────────────────


class FollowRequestModelTests(TestCase):
    """Tests for the FollowRequest model."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')

    def test_str(self):
        fr = FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.assertEqual(str(fr), 'alice \u2192 bob')

    def test_unique_together(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)

    def test_reverse_follow_request_allowed(self):
        """alice -> bob and bob -> alice should both be allowed."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        fr2 = FollowRequest.objects.create(from_user=self.bob, to_user=self.alice)
        self.assertEqual(str(fr2), 'bob \u2192 alice')

    def test_ordering(self):
        """FollowRequests are ordered by -created_at."""
        fr1 = FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        charlie = _make_user('charlie')
        fr2 = FollowRequest.objects.create(from_user=charlie, to_user=self.bob)
        requests = list(FollowRequest.objects.all())
        self.assertEqual(requests[0], fr2)  # Most recent first


# ─── User follower_count property ────────────────────────────────────


class UserFollowerCountTests(TestCase):
    """Tests for User.follower_count property."""

    def test_follower_count_zero(self):
        user = _make_user()
        self.assertEqual(user.follower_count, 0)

    def test_follower_count_after_follows(self):
        target = _make_user('target')
        f1 = _make_user('f1')
        f2 = _make_user('f2')
        f3 = _make_user('f3')
        f1.following.add(target)
        f2.following.add(target)
        f3.following.add(target)
        self.assertEqual(target.follower_count, 3)

    def test_follower_count_after_unfollow(self):
        target = _make_user('target')
        f1 = _make_user('f1')
        f1.following.add(target)
        self.assertEqual(target.follower_count, 1)
        f1.following.remove(target)
        self.assertEqual(target.follower_count, 0)


# ─── NoteAdmin ────────────────────────────────────────────────────────


class NoteAdminTests(TestCase):
    """Tests for NoteAdmin custom display methods."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = NoteAdmin(Note, self.site)
        self.user = _make_user()

    def test_title_preview_short(self):
        note = Note.objects.create(
            owner=self.user,
            title='Short title',
            content='Some content',
        )
        result = self.admin.title_preview(note)
        self.assertEqual(result, 'Short title')

    def test_title_preview_long(self):
        long_title = 'A' * 60
        note = Note.objects.create(
            owner=self.user,
            title=long_title,
            content='Some content',
        )
        result = self.admin.title_preview(note)
        self.assertEqual(result, 'A' * 50 + '...')
        self.assertEqual(len(result), 53)

    def test_title_preview_exactly_50(self):
        title_50 = 'B' * 50
        note = Note.objects.create(
            owner=self.user,
            title=title_50,
            content='Some content',
        )
        result = self.admin.title_preview(note)
        self.assertEqual(result, title_50)


# ─── PostFlagAdmin ────────────────────────────────────────────────────


class PostFlagAdminTests(TestCase):
    """Tests for PostFlagAdmin.post_preview."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = PostFlagAdmin(PostFlag, self.site)
        self.user = _make_user()

    def test_post_preview_short(self):
        post = Post.objects.create(
            author=self.user,
            content='Short post content',
        )
        flag = PostFlag.objects.create(
            post=post,
            reporter=self.user,
            reason=PostFlag.Reason.SPAM,
        )
        result = self.admin.post_preview(flag)
        self.assertEqual(result, 'Short post content')

    def test_post_preview_long(self):
        long_content = 'X' * 50
        post = Post.objects.create(
            author=self.user,
            content=long_content,
        )
        flag = PostFlag.objects.create(
            post=post,
            reporter=self.user,
            reason=PostFlag.Reason.HARASSMENT,
        )
        result = self.admin.post_preview(flag)
        self.assertEqual(result, 'X' * 40 + '...')

    def test_post_preview_exactly_40(self):
        content_40 = 'Z' * 40
        post = Post.objects.create(
            author=self.user,
            content=content_40,
        )
        flag = PostFlag.objects.create(
            post=post,
            reporter=self.user,
            reason=PostFlag.Reason.OTHER,
        )
        result = self.admin.post_preview(flag)
        self.assertEqual(result, content_40)


# ─── PostAdmin ────────────────────────────────────────────────────────


class PostAdminTests(TestCase):
    """Tests for PostAdmin custom display methods."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = PostAdmin(Post, self.site)
        self.user = _make_user()

    def test_content_preview_short(self):
        post = Post.objects.create(author=self.user, content='Short')
        result = self.admin.content_preview(post)
        self.assertEqual(result, 'Short')

    def test_content_preview_long(self):
        post = Post.objects.create(author=self.user, content='Y' * 60)
        result = self.admin.content_preview(post)
        self.assertEqual(result, 'Y' * 50 + '...')

    def test_like_count(self):
        post = Post.objects.create(author=self.user, content='Likes test')
        Like.objects.create(user=self.user, post=post)
        user2 = _make_user('user2')
        Like.objects.create(user=user2, post=post)
        result = self.admin.like_count(post)
        self.assertEqual(result, 2)

    def test_comment_count(self):
        post = Post.objects.create(author=self.user, content='Comments test')
        Comment.objects.create(author=self.user, post=post, content='c1')
        Comment.objects.create(author=self.user, post=post, content='c2')
        result = self.admin.comment_count(post)
        self.assertEqual(result, 2)


# ─── CommentAdmin ─────────────────────────────────────────────────────


class CommentAdminTests(TestCase):
    """Tests for CommentAdmin custom display methods."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = CommentAdmin(Comment, self.site)
        self.user = _make_user()

    def test_post_preview_short(self):
        post = Post.objects.create(author=self.user, content='Short post')
        comment = Comment.objects.create(author=self.user, post=post, content='Comment')
        result = self.admin.post_preview(comment)
        self.assertEqual(result, 'Short post')

    def test_post_preview_long(self):
        post = Post.objects.create(author=self.user, content='P' * 40)
        comment = Comment.objects.create(author=self.user, post=post, content='Comment')
        result = self.admin.post_preview(comment)
        self.assertEqual(result, 'P' * 30 + '...')

    def test_content_preview_short(self):
        post = Post.objects.create(author=self.user, content='Post')
        comment = Comment.objects.create(author=self.user, post=post, content='Short comment')
        result = self.admin.content_preview(comment)
        self.assertEqual(result, 'Short comment')

    def test_content_preview_long(self):
        post = Post.objects.create(author=self.user, content='Post')
        comment = Comment.objects.create(author=self.user, post=post, content='C' * 60)
        result = self.admin.content_preview(comment)
        self.assertEqual(result, 'C' * 50 + '...')


# ─── LikeAdmin / BookmarkAdmin ───────────────────────────────────────


class LikeAdminTests(TestCase):
    """Tests for LikeAdmin.post_preview."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = LikeAdmin(Like, self.site)
        self.user = _make_user()

    def test_post_preview_short(self):
        post = Post.objects.create(author=self.user, content='Short')
        like = Like.objects.create(user=self.user, post=post)
        self.assertEqual(self.admin.post_preview(like), 'Short')

    def test_post_preview_long(self):
        post = Post.objects.create(author=self.user, content='L' * 50)
        like = Like.objects.create(user=self.user, post=post)
        self.assertEqual(self.admin.post_preview(like), 'L' * 40 + '...')


class BookmarkAdminTests(TestCase):
    """Tests for BookmarkAdmin.post_preview."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BookmarkAdmin(Bookmark, self.site)
        self.user = _make_user()

    def test_post_preview_short(self):
        post = Post.objects.create(author=self.user, content='Short')
        bm = Bookmark.objects.create(user=self.user, post=post)
        self.assertEqual(self.admin.post_preview(bm), 'Short')

    def test_post_preview_long(self):
        post = Post.objects.create(author=self.user, content='K' * 50)
        bm = Bookmark.objects.create(user=self.user, post=post)
        self.assertEqual(self.admin.post_preview(bm), 'K' * 40 + '...')


# ─── Signals ──────────────────────────────────────────────────────────


class SocialAccountSignalTests(TestCase):
    """Tests for the on_social_account_linked signal handler."""

    def test_signal_adds_success_message(self):
        from timeout.signals import on_social_account_linked

        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'Google'

        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(
                request=mock_request,
                sociallogin=mock_sociallogin,
            )
            mock_messages.success.assert_called_once_with(
                mock_request,
                'Your Google account has been linked successfully!',
            )

    def test_signal_with_github_provider(self):
        from timeout.signals import on_social_account_linked

        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'GitHub'

        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(
                request=mock_request,
                sociallogin=mock_sociallogin,
            )
            mock_messages.success.assert_called_once_with(
                mock_request,
                'Your GitHub account has been linked successfully!',
            )

    def test_signal_with_discord_provider(self):
        from timeout.signals import on_social_account_linked

        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'Discord'

        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(
                request=mock_request,
                sociallogin=mock_sociallogin,
            )
            mock_messages.success.assert_called_once_with(
                mock_request,
                'Your Discord account has been linked successfully!',
            )


# ─── Social Views ────────────────────────────────────────────────────


class UserProfileOwnTests(TestCase):
    """Tests for viewing your own profile (incoming_requests path)."""

    def setUp(self):
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_own_profile_shows_incoming_requests(self):
        """When viewing own profile, incoming_requests should be in context."""
        bob = _make_user('bob')
        FollowRequest.objects.create(from_user=bob, to_user=self.user)

        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('incoming_requests', resp.context)
        # incoming_requests should contain the follow request from bob
        incoming = list(resp.context['incoming_requests'])
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].from_user, bob)

    def test_own_profile_no_incoming_requests(self):
        """Own profile with no incoming requests."""
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        incoming = list(resp.context['incoming_requests'])
        self.assertEqual(len(incoming), 0)

    def test_other_profile_no_incoming_requests(self):
        """Viewing someone else's profile should have empty incoming_requests."""
        bob = _make_user('bob')
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['incoming_requests']), [])

    def test_own_profile_has_pending_request_is_false(self):
        """has_pending_request should be False for own profile."""
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertFalse(resp.context['has_pending_request'])


class SearchUsersTests(TestCase):
    """Tests for the search_users view."""

    def setUp(self):
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_search_empty_query(self):
        resp = self.client.get(reverse('search_users'), {'q': ''})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_no_query_param(self):
        resp = self.client.get(reverse('search_users'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_whitespace_only(self):
        resp = self.client.get(reverse('search_users'), {'q': '   '})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_finds_user_by_username(self):
        _make_user('bob', first_name='Bob', last_name='Smith')
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('bob', usernames)

    def test_search_finds_user_by_first_name(self):
        _make_user('carol', first_name='Carol')
        resp = self.client.get(reverse('search_users'), {'q': 'Carol'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('carol', usernames)

    def test_search_excludes_self(self):
        resp = self.client.get(reverse('search_users'), {'q': 'alice'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('alice', usernames)

    def test_search_no_results(self):
        resp = self.client.get(reverse('search_users'), {'q': 'nonexistentuser123'})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])


class FollowersAPITests(TestCase):
    """Tests for followers_api view."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_followers_api_empty(self):
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_followers_api_with_followers(self):
        self.bob.following.add(self.alice)  # bob follows alice
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_followers_api_includes_follow_back_info(self):
        self.bob.following.add(self.alice)  # bob follows alice
        self.alice.following.add(self.bob)  # alice follows bob back
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertTrue(data['users'][0]['is_followed_back'])

    def test_followers_api_not_followed_back(self):
        self.bob.following.add(self.alice)  # bob follows alice, alice does NOT follow back
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertFalse(data['users'][0]['is_followed_back'])

    def test_followers_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 302)


class FollowingAPITests(TestCase):
    """Tests for following_api view."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_following_api_empty(self):
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_following_api_with_following(self):
        self.alice.following.add(self.bob)  # alice follows bob
        resp = self.client.get(reverse('following_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_following_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 302)


class FriendsAPITests(TestCase):
    """Tests for friends_api view."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.charlie = _make_user('charlie')
        self.client.login(username='alice', password='TestPass1!')

    def test_friends_api_empty(self):
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_mutual_follow(self):
        # Mutual follow = friends
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_friends_api_one_way_not_friend(self):
        # Alice follows bob, but bob does not follow alice
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 302)


class UserFollowersAPIPrivateTests(TestCase):
    """Tests for user_followers_api and user_following_api with private accounts."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_followers_api_private_forbidden(self):
        resp = self.client.get(
            reverse('user_followers_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_following_api_private_forbidden(self):
        resp = self.client.get(
            reverse('user_following_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_followers_api_private_allowed_if_following(self):
        """If alice follows the private user, she can see their followers."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(
            reverse('user_followers_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_allowed_if_following(self):
        """If alice follows the private user, she can see their following."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(
            reverse('user_following_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_own_profile_allowed(self):
        """User can always view their own followers."""
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(
            reverse('user_followers_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_own_profile_allowed(self):
        """User can always view their own following."""
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(
            reverse('user_following_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_public_always_allowed(self):
        """Public accounts' followers are always accessible."""
        public_user = _make_user('public_user', privacy_private=False)
        resp = self.client.get(
            reverse('user_followers_api', args=['public_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_public_always_allowed(self):
        """Public accounts' following are always accessible."""
        public_user = _make_user('public_user', privacy_private=False)
        resp = self.client.get(
            reverse('user_following_api', args=['public_user'])
        )
        self.assertEqual(resp.status_code, 200)


class UserFriendsAPIPrivateTests(TestCase):
    """Tests for user_friends_api with private accounts."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_friends_api_private_forbidden(self):
        resp = self.client.get(
            reverse('user_friends_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_friends_api_private_allowed_if_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(
            reverse('user_friends_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_own(self):
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(
            reverse('user_friends_api', args=['private_user'])
        )
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_public(self):
        public = _make_user('pubuser', privacy_private=False)
        resp = self.client.get(
            reverse('user_friends_api', args=['pubuser'])
        )
        self.assertEqual(resp.status_code, 200)


class UserProfileViewTests(TestCase):
    """Additional tests for user_profile view covering different paths."""

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.private_user = _make_user('private_carol', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_view_public_user_profile(self):
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])

    def test_view_private_user_profile_not_following(self):
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['can_view'])

    def test_view_private_user_profile_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])
        self.assertTrue(resp.context['is_following'])

    def test_view_profile_context_keys(self):
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertIn('profile_user', resp.context)
        self.assertIn('posts', resp.context)
        self.assertIn('is_following', resp.context)
        self.assertIn('can_view', resp.context)
        self.assertIn('friends_count', resp.context)
        self.assertIn('has_pending_request', resp.context)
        self.assertIn('incoming_requests', resp.context)

    def test_view_profile_with_pending_request(self):
        """has_pending_request should be True if alice sent a follow request."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertTrue(resp.context['has_pending_request'])

    def test_profile_friends_count(self):
        """friends_count is correct for a public user."""
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.context['friends_count'], 1)

    def test_profile_friends_count_private_not_viewable(self):
        """friends_count should be 0 when profile is not viewable."""
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.context['friends_count'], 0)
