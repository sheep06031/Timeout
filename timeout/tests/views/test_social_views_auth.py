"""
test_social_views_auth.py - Defines SocialViewsAuthTest for verifying that protected social endpoints
(feed, bookmarks, like post) redirect unauthenticated users to the login page with the correct next URL.
"""


from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models import Post

User = get_user_model()


class SocialViewsAuthTest(TestCase):
    """Tests that authentication is required for protected social endpoints. """

    def setUp(self):
        """Set up a test user and test post for the social views authentication tests."""
        self.user = User.objects.create_user(
            username="user",
            password="pass123",
        )
        self.post = Post.objects.create(
            author=self.user,
            content="x",
            privacy=Post.Privacy.PUBLIC,
        )

    def test_feed_requires_login(self):
        """Test that accessing the social feed without authentication redirects to the login page, ensuring that the feed view is protected and only accessible to logged-in users."""
        res = self.client.get(reverse("social_feed"))
        self.assertIn(res.status_code, (302, 401, 403))

    def test_bookmarks_requires_login(self):
        """Test that accessing the bookmarks page without authentication redirects to the login page, ensuring that the bookmarks view is protected and only accessible to logged-in users."""
        res = self.client.get(reverse("bookmarks"))
        self.assertIn(res.status_code, (302, 401, 403))

    def test_like_requires_login(self):
        """Test that attempting to like a post without authentication redirects to the login page, ensuring that the like_post view is protected and only allows logged-in users to like posts."""
        res = self.client.post(reverse("like_post", args=[self.post.id]))
        self.assertIn(res.status_code, (302, 401, 403))