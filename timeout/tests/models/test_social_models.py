"""
test_social_models.py - Defines SocialModelsTest for testing the social-related models (Post, Comment, Like, Bookmark) in the application, including their methods,
constraints, and behavior with authenticated and anonymous users.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.contrib.auth.models import AnonymousUser

from timeout.models import Post, Comment, Like, Bookmark

User = get_user_model()


class SocialModelsTest(TestCase):
    """Coverage-focused tests for social-related model helpers and constraints."""

    def setUp(self):
        """Set up test users and posts for social model tests."""
        self.author = User.objects.create_user(username="author", password="pass123")
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")

        self.public_post = Post.objects.create(
            author=self.author,
            content="public",
            privacy=Post.Privacy.PUBLIC,
        )
        self.private_post = Post.objects.create(
            author=self.author,
            content="followers only",
            privacy=Post.Privacy.FOLLOWERS_ONLY,
        )

    def test_post_like_count_and_is_liked_by(self):
        """Test that like count and is_liked_by() work correctly."""
        self.assertEqual(self.public_post.get_like_count(), 0)
        self.assertFalse(self.public_post.is_liked_by(self.u1))

        Like.objects.create(user=self.u1, post=self.public_post)
        self.assertEqual(self.public_post.get_like_count(), 1)
        self.assertTrue(self.public_post.is_liked_by(self.u1))

    def test_like_unique_together(self):
        """Test that the Like model enforces unique(user, post)."""
        Like.objects.create(user=self.u1, post=self.public_post)
        with self.assertRaises(IntegrityError):
            Like.objects.create(user=self.u1, post=self.public_post)

    def test_bookmark_unique_together_and_is_bookmarked_by(self):
        """Test that the Bookmark model enforces unique(user, post) and is_bookmarked_by() works correctly."""
        self.assertFalse(self.public_post.is_bookmarked_by(self.u1))
        Bookmark.objects.create(user=self.u1, post=self.public_post)
        self.assertTrue(self.public_post.is_bookmarked_by(self.u1))

        with self.assertRaises(IntegrityError):
            Bookmark.objects.create(user=self.u1, post=self.public_post)

    def test_comment_reply_helpers_and_delete_permission(self):
        """Test that comment reply helpers and delete permission logic work correctly."""
        c1 = Comment.objects.create(post=self.public_post, author=self.u1, content="parent")
        self.assertFalse(c1.is_reply())
        self.assertEqual(c1.get_reply_count(), 0)

        reply = Comment.objects.create(post=self.public_post, author=self.u2, content="reply", parent=c1)
        self.assertTrue(reply.is_reply())
        self.assertEqual(c1.get_reply_count(), 1)

        self.assertTrue(c1.can_delete(self.u1))
        self.assertFalse(c1.can_delete(self.u2))

        self.u2.is_staff = True
        self.u2.save()
        self.assertTrue(c1.can_delete(self.u2))

    def test_post_can_delete(self):
        """Test that post delete permissions work correctly."""
        self.assertTrue(self.public_post.can_delete(self.author))
        self.assertFalse(self.public_post.can_delete(self.u1))

        self.u1.is_staff = True
        self.u1.save()
        self.assertTrue(self.public_post.can_delete(self.u1))

    def test_post_can_view_public(self):
        """Test that public posts can be viewed by any authenticated user."""
        self.assertTrue(self.public_post.can_view(self.u1))

    def test_post_can_view_followers_only(self):
        """Test that followers-only posts can be viewed by followers."""
        self.assertFalse(self.private_post.can_view(self.u1))

        self.u1.following.add(self.author)
        self.assertTrue(self.private_post.can_view(self.u1))

        # Author should always see their own post
        self.assertTrue(self.private_post.can_view(self.author))

    def test_post_str_and_unauth_branches_and_comment_count(self):
        """Test the string representation, anonymous user branches, and comment count."""
        s = str(self.public_post)
        self.assertIn(self.author.username, s)

        anon = AnonymousUser()

        # Anonymous users cannot like/bookmark
        self.assertFalse(self.public_post.is_liked_by(anon))
        self.assertFalse(self.public_post.is_bookmarked_by(anon))

        Comment.objects.create(post=self.public_post, author=self.u1, content="c")
        self.assertEqual(self.public_post.get_comment_count(), 1)

        # Anonymous visibility and delete checks
        self.assertFalse(self.private_post.can_view(anon))
        self.assertFalse(self.public_post.can_delete(anon))

    def test_comment_str_and_can_delete_unauth(self):
        """Test the string representation of comments and delete permission for anonymous users."""
        c = Comment.objects.create(
            post=self.public_post,
            author=self.u1,
            content="x" * 40
        )
        self.assertIn(self.u1.username, str(c))

        anon = AnonymousUser()
        self.assertFalse(c.can_delete(anon))

    def test_like_str(self):
        """Test the string representation of likes."""
        like = Like.objects.create(user=self.u1, post=self.public_post)
        self.assertIn("likes", str(like))

    def test_bookmark_str(self):
        """Test the string representation of bookmarks."""
        bm = Bookmark.objects.create(user=self.u1, post=self.public_post)
        self.assertIn("bookmarked", str(bm))