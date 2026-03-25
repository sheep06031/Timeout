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
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def approve_url(self, flag_id=None):
        return reverse("approve_flag", args=[flag_id or self.flag.id])

    # Staff can approve a flag: post is deleted
    def test_staff_can_approve_flag(self):
        self.login(self.staff)
        post_id = self.post.id
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["ok"])
        self.assertFalse(Post.objects.filter(id=post_id).exists())

    # Approving deletes all associated flags via cascade
    def test_approve_cascades_all_flags(self):
        PostFlag.objects.create(post=self.post, reporter=self.staff, reason="other")
        self.login(self.staff)
        self.client.post(self.approve_url())
        self.assertFalse(PostFlag.objects.filter(post_id=self.post.id).exists())

    # Approving creates a notification for the post author
    def test_approve_notifies_author(self):
        self.login(self.staff)
        self.client.post(self.approve_url())
        self.assertTrue(
            Notification.objects.filter(
                user=self.author, title="⚠️ Post Removed",
            ).exists()
        )

    # Non-staff user gets 403
    def test_non_staff_gets_403(self):
        self.login(self.reporter)
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

    # Unauthenticated user is redirected to login
    def test_requires_login(self):
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_rejects_get(self):
        self.login(self.staff)
        response = self.client.get(self.approve_url())
        self.assertEqual(response.status_code, 405)

    # Approving a nonexistent flag returns 404
    def test_nonexistent_flag_returns_404(self):
        self.login(self.staff)
        response = self.client.post(self.approve_url(flag_id=99999))
        self.assertEqual(response.status_code, 404)


class DenyFlagViewTest(TestCase):
    """Tests for the deny_flag view."""

    def setUp(self):
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
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def deny_url(self, flag_id=None):
        return reverse("deny_flag", args=[flag_id or self.flag.id])

    # Staff can deny a flag: flag removed, post untouched
    def test_staff_can_deny_flag(self):
        self.login(self.staff)
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["ok"])
        self.assertFalse(PostFlag.objects.filter(id=self.flag.id).exists())
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

    # Denying does not notify the post author
    def test_deny_does_not_notify_author(self):
        self.login(self.staff)
        self.client.post(self.deny_url())
        self.assertFalse(Notification.objects.filter(user=self.author).exists())

    # Non-staff user gets 403
    def test_non_staff_gets_403(self):
        self.login(self.reporter)
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PostFlag.objects.filter(id=self.flag.id).exists())

    # Unauthenticated user is redirected to login
    def test_requires_login(self):
        response = self.client.post(self.deny_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_rejects_get(self):
        self.login(self.staff)
        response = self.client.get(self.deny_url())
        self.assertEqual(response.status_code, 405)

    # Denying a nonexistent flag returns 404
    def test_nonexistent_flag_returns_404(self):
        self.login(self.staff)
        response = self.client.post(self.deny_url(flag_id=99999))
        self.assertEqual(response.status_code, 404)


class ReviewFlagsTabTest(TestCase):
    """Tests for the review_flags tab on the social feed."""

    def setUp(self):
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
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def feed_url(self, tab):
        return reverse("social_feed") + f"?tab={tab}"

    # Staff sees pending flags on the review_flags tab
    def test_staff_sees_flags(self):
        self.login(self.staff)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("flags", response.context)
        self.assertEqual(len(response.context["flags"]), 1)

    # Non-staff gets no flags (falls back to following tab)
    def test_non_staff_gets_no_flags(self):
        self.login(self.user)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context.get("flags", [])), 0)

    # Active tab is review_flags when staff requests it
    def test_active_tab_is_review_flags_for_staff(self):
        self.login(self.staff)
        response = self.client.get(self.feed_url("review_flags"))
        self.assertEqual(response.context["active_tab"], "review_flags")
