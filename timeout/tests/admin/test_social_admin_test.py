"""
test_social_admin_test.py - Defines SocialAdminCoverageTest for testing admin helper methods in PostAdmin, CommentAdmin, LikeAdmin, and BookmarkAdmin.
This test case focuses on coverage of methods that generate content previews and count related objects, without testing the admin UI itself.
"""


from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

from timeout.models import Post, Comment, Like, Bookmark
from timeout.admin.social_admin import PostAdmin, CommentAdmin, LikeAdmin, BookmarkAdmin

User = get_user_model()


class SocialAdminCoverageTest(TestCase):
    """Coverage-only tests for admin helper methods (does not test admin UI)."""

    def setUp(self):
        """Set up users and admin site for tests."""
        self.site = AdminSite()
        self.author = User.objects.create_user(username="author", password="pass123")
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")

    def test_post_admin_preview_and_counts(self):
        """ PostAdmin has methods for content preview, like count, and comment count """
        pa = PostAdmin(Post, self.site)

        short = Post(author=self.author, content="short", privacy=Post.Privacy.PUBLIC)
        long = Post(author=self.author, content="x" * 60, privacy=Post.Privacy.PUBLIC)

        self.assertEqual(pa.content_preview(short), "short")
        self.assertTrue(pa.content_preview(long).endswith("..."))

        saved = Post.objects.create(author=self.author, content="counts", privacy=Post.Privacy.PUBLIC)
        Like.objects.create(user=self.u1, post=saved)
        Comment.objects.create(post=saved, author=self.u2, content="c")

        self.assertEqual(pa.like_count(saved), 1)
        self.assertEqual(pa.comment_count(saved), 1)

    def test_comment_admin_previews(self):
        """ CommentAdmin has methods for post content preview and comment content preview """
        ca = CommentAdmin(Comment, self.site)

        p_short = Post.objects.create(author=self.author, content="a" * 10, privacy=Post.Privacy.PUBLIC)
        p_long = Post.objects.create(author=self.author, content="b" * 40, privacy=Post.Privacy.PUBLIC)

        c_short_post = Comment.objects.create(post=p_short, author=self.u1, content="hi")
        c_long_post = Comment.objects.create(post=p_long, author=self.u1, content="hi")
        c_long_content = Comment.objects.create(post=p_short, author=self.u1, content="x" * 60)

        self.assertEqual(ca.post_preview(c_short_post), "a" * 10)
        self.assertTrue(ca.post_preview(c_long_post).endswith("..."))

        self.assertEqual(ca.content_preview(c_short_post), "hi")
        self.assertTrue(ca.content_preview(c_long_content).endswith("..."))

    def test_like_and_bookmark_admin_post_preview(self):
        """ LikeAdmin and BookmarkAdmin have a method for post content preview"""
        la = LikeAdmin(Like, self.site)
        ba = BookmarkAdmin(Bookmark, self.site)

        p_short = Post.objects.create(author=self.author, content="c" * 20, privacy=Post.Privacy.PUBLIC)
        p_long = Post.objects.create(author=self.author, content="d" * 60, privacy=Post.Privacy.PUBLIC)

        like_short = Like.objects.create(user=self.u1, post=p_short)
        like_long = Like.objects.create(user=self.u2, post=p_long)
        bm_short = Bookmark.objects.create(user=self.u1, post=p_short)
        bm_long = Bookmark.objects.create(user=self.u2, post=p_long)

        self.assertEqual(la.post_preview(like_short), "c" * 20)
        self.assertTrue(la.post_preview(like_long).endswith("..."))

        self.assertEqual(ba.post_preview(bm_short), "c" * 20)
        self.assertTrue(ba.post_preview(bm_long).endswith("..."))