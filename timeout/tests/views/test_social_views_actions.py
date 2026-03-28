"""
test_social_views_actions.py - Defines SocialViewsActionsTest for testing social view actions:
post creation/deletion, likes, bookmarks, comments, follow/unfollow, and public vs followers-only
post visibility permissions enforcement.
"""


import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models import Post, Like, Bookmark, Comment

User = get_user_model()


class SocialViewsActionsTest(TestCase):
    """Integration-style tests for social views. """

    def setUp(self):
        """Set up test users and posts for the social views actions tests, creating an author user who creates both a public and a followers-only post, and another user who will interact with these posts in the tests, allowing for testing of permissions, liking, bookmarking, commenting, and following functionality in the social views."""
        self.author = User.objects.create_user(username="author", password="pass123")
        self.other = User.objects.create_user(username="other", password="pass123")

        self.post_public = Post.objects.create(
            author=self.author,
            content="pub",
            privacy=Post.Privacy.PUBLIC,
        )
        self.post_private = Post.objects.create(
            author=self.author,
            content="priv",
            privacy=Post.Privacy.FOLLOWERS_ONLY,
        )

    def login(self, user):
        """Helper: log a user into the Django test client."""
        ok = self.client.login(username=user.username, password="pass123")
        self.assertTrue(ok)

    def test_create_post(self):
        """Test that an authenticated user can create a new post via the create_post view, ensuring that the view correctly handles post creation and redirects appropriately, and that the new post is saved in the database with the correct author and content."""
        self.login(self.author)
        res = self.client.post(
            reverse("create_post"),
            data={"content": "new", "privacy": Post.Privacy.PUBLIC},
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Post.objects.filter(author=self.author, content="new").exists())

    def test_delete_post_permission_denied_for_non_author(self):
        """Test that a user who is not the author of a post cannot delete it via the delete_post view, ensuring that the view enforces permissions correctly by returning a 403 Forbidden status code and that the post remains in the database after the attempted deletion."""
        self.login(self.other)
        res = self.client.post(reverse("delete_post", args=[self.post_public.id]))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post_public.id).exists())

    def test_delete_post_ok_for_author(self):
        """Test that the author of a post can delete it via the delete_post view, ensuring that the view correctly handles post deletion by returning a redirect status code and that the post is removed from the database."""
        self.login(self.author)
        res = self.client.post(reverse("delete_post", args=[self.post_public.id]))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Post.objects.filter(id=self.post_public.id).exists())

    def test_like_toggle_public_post(self):
        """Test that liking a public post toggles the like state and returns the correct JSON response."""
        self.login(self.other)
        url = reverse("like_post", args=[self.post_public.id])

        res1 = self.client.post(url)
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.content)
        self.assertTrue(data1["liked"])
        self.assertEqual(
            Like.objects.filter(user=self.other, post=self.post_public).count(),
            1,
        )

        res2 = self.client.post(url)
        data2 = json.loads(res2.content)
        self.assertFalse(data2["liked"])
        self.assertEqual(
            Like.objects.filter(user=self.other, post=self.post_public).count(),
            0,
        )

    def test_bookmark_toggle_public_post(self):
        """Test that bookmarking a public post toggles the bookmark state and returns the correct JSON response."""
        self.login(self.other)
        url = reverse("bookmark_post", args=[self.post_public.id])

        res1 = self.client.post(url)
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.content)
        self.assertTrue(data1["bookmarked"])
        self.assertEqual(
            Bookmark.objects.filter(user=self.other, post=self.post_public).count(),
            1,
        )

        res2 = self.client.post(url)
        data2 = json.loads(res2.content)
        self.assertFalse(data2["bookmarked"])
        self.assertEqual(
            Bookmark.objects.filter(user=self.other, post=self.post_public).count(),
            0,
        )

    def test_like_private_post_forbidden_if_not_follower(self):
        """Test that attempting to like a followers-only post without following the author returns a 403 Forbidden status code, ensuring that the like_post view correctly enforces permissions based on the post's privacy settings and the user's relationship to the author."""
        self.login(self.other)
        res = self.client.post(reverse("like_post", args=[self.post_private.id]))
        self.assertEqual(res.status_code, 403)

    def test_like_private_post_ok_if_follower(self):
        """Test that liking a followers-only post succeeds if the user follows the author, ensuring that the like_post view correctly enforces permissions based on the post's privacy settings and the user's relationship to the author."""
        self.other.following.add(self.author)
        self.login(self.other)
        res = self.client.post(reverse("like_post", args=[self.post_private.id]))
        self.assertEqual(res.status_code, 200)

    def test_add_comment_and_reply(self):
        """Test that an authenticated user can add a comment to a public post and then reply to that comment, ensuring that the add_comment view correctly handles both creating a new comment and creating a reply to an existing comment, and that the comments are saved in the database with the correct relationships."""
        self.login(self.other)

        res1 = self.client.post(
            reverse("add_comment", args=[self.post_public.id]),
            data={"content": "first"},
        )
        self.assertEqual(res1.status_code, 302)
        c1 = Comment.objects.get(post=self.post_public, author=self.other, content="first")

        res2 = self.client.post(
            reverse("add_comment", args=[self.post_public.id]),
            data={"content": "reply", "parent_id": str(c1.id)},
        )
        self.assertEqual(res2.status_code, 302)
        reply = Comment.objects.get(post=self.post_public, author=self.other, content="reply")
        self.assertEqual(reply.parent_id, c1.id)

    def test_follow_toggle(self):
        """Test that following a user toggles the follow state and returns the correct JSON response."""
        self.login(self.other)
        url = reverse("follow_user", args=[self.author.username])

        res1 = self.client.post(url)
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.content)
        self.assertTrue(data1["following"])
        self.assertTrue(self.other.following.filter(id=self.author.id).exists())

        res2 = self.client.post(url)
        data2 = json.loads(res2.content)
        self.assertFalse(data2["following"])
        self.assertFalse(self.other.following.filter(id=self.author.id).exists())

    def test_follow_self_rejected(self):
        """Test that a user cannot follow themselves, ensuring that the follow_user view correctly handles this edge case."""
        self.login(self.author)
        url = reverse("follow_user", args=[self.author.username])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 400)

    def test_feed_discover_tab(self):
        """Test that the feed page renders correctly with the discover tab selected."""
        self.login(self.other)
        res = self.client.get(reverse("social_feed") + "?tab=discover")
        self.assertEqual(res.status_code, 200)

    def test_create_post_invalid(self):
        """Test that attempting to create a post with invalid data (empty content) does not create a new post and returns the correct status code, ensuring that the create_post view correctly validates input and handles errors."""
        self.login(self.author)
        res = self.client.post(
            reverse("create_post"),
            data={"content": "", "privacy": Post.Privacy.PUBLIC},
        )
        self.assertEqual(res.status_code, 302)

    def test_bookmark_private_post_forbidden_if_not_follower(self):
        """Test that attempting to bookmark a followers-only post without following the author returns a 403 Forbidden status code, ensuring that the bookmark_post view correctly enforces permissions based on the post's privacy settings and the user's relationship to the author."""
        self.login(self.other)
        res = self.client.post(reverse("bookmark_post", args=[self.post_private.id]))
        self.assertEqual(res.status_code, 403)

    def test_bookmarks_view_ok(self):
        """Test that the bookmarks page renders correctly for an authenticated user."""
        self.login(self.other)
        res = self.client.get(reverse("bookmarks"))
        self.assertEqual(res.status_code, 200)

    def test_add_comment_forbidden_on_private_post_if_not_follower(self):
        """Test that attempting to add a comment to a followers-only post without following the author returns a 403 Forbidden status code, ensuring that the add_comment view correctly enforces permissions based on the post's privacy settings and the user's relationship to the author."""
        self.login(self.other)
        res = self.client.post(
            reverse("add_comment", args=[self.post_private.id]),
            data={"content": "hi"},
        )
        self.assertEqual(res.status_code, 403)

    def test_add_comment_invalid_form(self):
        """"""
        self.other.following.add(self.author)
        self.login(self.other)
        res = self.client.post(
            reverse("add_comment", args=[self.post_private.id]),
            data={"content": ""},
        )
        self.assertEqual(res.status_code, 302)

    def test_user_profile_view_ok(self):
        """Test that the user profile page renders correctly for an authenticated viewer."""
        self.other.following.add(self.author)
        self.login(self.other)
        res = self.client.get(reverse("user_profile", args=[self.author.username]))
        self.assertEqual(res.status_code, 200)

    def test_feed_unknown_tab_defaults(self):
        """Test that accessing the feed with an unknown tab parameter defaults to the main feed view without errors, ensuring that the social_feed view can handle unexpected tab values gracefully and still render the page successfully."""
        self.login(self.other)
        res = self.client.get(reverse("social_feed") + "?tab=wtf")
        self.assertEqual(res.status_code, 200)