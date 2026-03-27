"""
Tests for model properties, admin display methods, and signals.
Covers: FollowRequest model, User.follower_count, NoteAdmin,
        PostFlagAdmin, PostAdmin, CommentAdmin, LikeAdmin,
        BookmarkAdmin, on_social_account_linked signal.
"""
from unittest.mock import patch, MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase

from timeout.admin.note_admin import NoteAdmin
from timeout.admin.social_admin import PostFlagAdmin, PostAdmin, CommentAdmin, LikeAdmin, BookmarkAdmin
from timeout.models import Post, Note, FollowRequest, PostFlag, Comment, Like, Bookmark

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# FollowRequest Model

class FollowRequestModelTests(TestCase):

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
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        fr2 = FollowRequest.objects.create(from_user=self.bob, to_user=self.alice)
        self.assertEqual(str(fr2), 'bob \u2192 alice')

    def test_ordering(self):
        fr1 = FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        charlie = _make_user('charlie')
        fr2 = FollowRequest.objects.create(from_user=charlie, to_user=self.bob)
        requests = list(FollowRequest.objects.all())
        self.assertEqual(requests[0], fr2)


# User follower_count property

class UserFollowerCountTests(TestCase):

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


# NoteAdmin

class NoteAdminTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = NoteAdmin(Note, self.site)
        self.user = _make_user()

    def test_title_preview_short(self):
        note = Note.objects.create(owner=self.user, title='Short title', content='Some content')
        result = self.admin.title_preview(note)
        self.assertEqual(result, 'Short title')

    def test_title_preview_long(self):
        long_title = 'A' * 60
        note = Note.objects.create(owner=self.user, title=long_title, content='Some content')
        result = self.admin.title_preview(note)
        self.assertEqual(result, 'A' * 50 + '...')
        self.assertEqual(len(result), 53)

    def test_title_preview_exactly_50(self):
        title_50 = 'B' * 50
        note = Note.objects.create(owner=self.user, title=title_50, content='Some content')
        result = self.admin.title_preview(note)
        self.assertEqual(result, title_50)


# PostFlagAdmin

class PostFlagAdminTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = PostFlagAdmin(PostFlag, self.site)
        self.user = _make_user()

    def test_post_preview_short(self):
        post = Post.objects.create(author=self.user, content='Short post content')
        flag = PostFlag.objects.create(post=post, reporter=self.user, reason=PostFlag.Reason.SPAM)
        result = self.admin.post_preview(flag)
        self.assertEqual(result, 'Short post content')

    def test_post_preview_long(self):
        post = Post.objects.create(author=self.user, content='X' * 50)
        flag = PostFlag.objects.create(post=post, reporter=self.user, reason=PostFlag.Reason.HARASSMENT)
        result = self.admin.post_preview(flag)
        self.assertEqual(result, 'X' * 40 + '...')

    def test_post_preview_exactly_40(self):
        content_40 = 'Z' * 40
        post = Post.objects.create(author=self.user, content=content_40)
        flag = PostFlag.objects.create(post=post, reporter=self.user, reason=PostFlag.Reason.OTHER)
        result = self.admin.post_preview(flag)
        self.assertEqual(result, content_40)


# PostAdmin

class PostAdminTests(TestCase):

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


# CommentAdmin

class CommentAdminTests(TestCase):

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


# LikeAdmin / BookmarkAdmin

class LikeAdminTests(TestCase):

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


# Signals

class SocialAccountSignalTests(TestCase):

    def test_signal_adds_success_message(self):
        from timeout.signals import on_social_account_linked
        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'Google'
        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(request=mock_request, sociallogin=mock_sociallogin)
            mock_messages.success.assert_called_once_with(
                mock_request, 'Your Google account has been linked successfully!',
            )

    def test_signal_with_github_provider(self):
        from timeout.signals import on_social_account_linked
        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'GitHub'
        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(request=mock_request, sociallogin=mock_sociallogin)
            mock_messages.success.assert_called_once_with(
                mock_request, 'Your GitHub account has been linked successfully!',
            )

    def test_signal_with_discord_provider(self):
        from timeout.signals import on_social_account_linked
        mock_request = MagicMock()
        mock_sociallogin = MagicMock()
        mock_sociallogin.account.get_provider.return_value.name = 'Discord'
        with patch('timeout.signals.messages') as mock_messages:
            on_social_account_linked(request=mock_request, sociallogin=mock_sociallogin)
            mock_messages.success.assert_called_once_with(
                mock_request, 'Your Discord account has been linked successfully!',
            )