"""
Tests for the flag review views in the timeout app, including approve_flag, deny_flag, and the review_flags tab on the social feed.
These tests ensure that the flag review functionality works correctly, enforces proper permissions, and handles various edge cases appropriately.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from timeout.models import Post, PostFlag
from timeout.models.notification import Notification

User = get_user_model()


class ApproveFlagViewTest(TestCase):
    """Tests for the approve_flag view."""

    def setUp(self):
        """Create a staff user, a regular user, an author, a post, and a flag for testing."""
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True,
        )
        self.reporter = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author, content="Bad content", privacy=Post.Privacy.PUBLIC,
        )
        self.flag = PostFlag.objects.create(
            post=self.post, reporter=self.reporter, reason="spam",
        )

    def login(self, user):
        """Helper method to log in a user."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def approve_url(self, flag_id=None):
        """Helper method to get the URL for approving a flag."""
        return reverse("approve_flag", args=[flag_id or self.flag.id])

    def test_staff_can_approve_flag(self):
        """A staff user should be able to approve a flag, which deletes the post."""
        self.login(self.staff)
        post_id = self.post.id
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertFalse(Post.objects.filter(id=post_id).exists())

    def test_approve_cascades_all_flags(self):
        """Approving one flag should remove all flags for that post."""
        PostFlag.objects.create(post=self.post, reporter=self.staff, reason="other")
        self.login(self.staff)
        self.client.post(self.approve_url())
        self.assertFalse(PostFlag.objects.filter(post_id=self.post.id).exists())

    def test_approve_notifies_author(self):
        """Approving a flag should notify the post author that their post was removed."""
        self.login(self.staff)
        self.client.post(self.approve_url())
        self.assertTrue(
            Notification.objects.filter(
                user=self.author, title="⚠️ Post Removed",
            ).exists()
        )

    def test_non_staff_gets_403(self):
        """A non-staff user should get a 403 Forbidden error when trying to approve a flag."""
        self.login(self.reporter)
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

    def test_requires_login(self):
        """An unauthenticated user should be redirected to the login page when trying to approve a flag."""
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_rejects_get(self):
        """The approve_flag view should reject GET requests (require POST)."""
        self.login(self.staff)
        response = self.client.get(self.approve_url())
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_flag_returns_404(self):
        """If the flag ID does not exist, should return a 404 error."""
        self.login(self.staff)
        response = self.client.post(self.approve_url(flag_id=99999))
        self.assertEqual(response.status_code, 404)


class DenyFlagViewTest(TestCase):
    """Tests for the deny_flag view."""

    def setUp(self):
        """Create a staff user, a regular user, an author, a post, and a flag for testing."""
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True,
        )
        self.reporter = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author, content="Fine content", privacy=Post.Privacy.PUBLIC,
        )
        self.flag = PostFlag.objects.create(
            post=self.post, reporter=self.reporter, reason="spam",
        )

    def login(self, user):
        """Helper method to log in a user."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def deny_url(self, flag_id=None):
        """Helper method to get the URL for denying a flag."""
        return reverse("deny_flag", args=[flag_id or self.flag.id])

    def test_staff_can_deny_flag(self):
        """A staff user should be able to deny a flag, which deletes the flag but keeps the post."""
        self.login(self.staff)
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertFalse(PostFlag.objects.filter(id=self.flag.id).exists())
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

    def test_deny_does_not_notify_author(self):
        """Denying a flag should not notify the post author, since their post is not removed."""
        self.login(self.staff)
        self.client.post(self.deny_url())
        self.assertFalse(Notification.objects.filter(user=self.author).exists())

    def test_non_staff_gets_403(self):
        """A non-staff user should get a 403 Forbidden error when trying to deny a flag."""
        self.login(self.reporter)
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PostFlag.objects.filter(id=self.flag.id).exists())

    def test_requires_login(self):
        """An unauthenticated user should be redirected to the login page when trying to deny a flag."""
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_rejects_get(self):
        """The deny_flag view should reject GET requests (require POST)."""
        self.login(self.staff)
        response = self.client.get(self.deny_url())
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_flag_returns_404(self):
        """If the flag ID does not exist, should return a 404 error."""
        self.login(self.staff)
        response = self.client.post(self.deny_url(flag_id=99999))
        self.assertEqual(response.status_code, 404)


class ReviewFlagsTabTest(TestCase):
    """Tests for the review_flags tab on the social feed."""

    def setUp(self):
        """Create a staff user, a regular user, an author, a post, and a flag for testing."""
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True,
        )
        self.user = User.objects.create_user(username="regular", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author, content="Flagged content", privacy=Post.Privacy.PUBLIC,
        )
        PostFlag.objects.create(post=self.post, reporter=self.user, reason="spam")

    def login(self, user):
        """Helper method to log in a user."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def feed_url(self, tab):
        """Helper method to get the URL for the social feed with a specific tab."""
        return reverse("social_feed") + f"?tab={tab}"

    def test_staff_sees_flags(self):
        """A staff user should see the list of flags in the review_flags tab."""
        self.login(self.staff)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("flags", response.context)
        self.assertEqual(len(response.context["flags"]), 1)

    def test_non_staff_gets_no_flags(self):
        """A non-staff user should not see any flags in the review_flags tab."""
        self.login(self.user)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context.get("flags", [])), 0)

    def test_active_tab_is_review_flags_for_staff(self):
        """When a staff user visits the review_flags tab, it should be marked as active."""
        self.login(self.staff)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.context["active_tab"], "review_flags")
