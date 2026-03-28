"""
Tests for the admin moderation views in the timeout app, including delete_comment, ban_user, and unban_user.
These tests cover various scenarios such as permissions (author, staff, non-author), HTTP methods (POST vs GET), existence of the target comment or user, and AJAX requests. 
The tests verify that the views behave as expected, including proper redirections, status codes, database changes (deletion of comments, banning/unbanning users), and messages shown to the user. 
Additionally, there are tests for the BannedUserMiddleware to ensure that banned users are properly logged out and redirected, and that non-banned users are unaffected.
"""
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, RequestFactory
from django.urls import reverse

from timeout.middleware import BannedUserMiddleware
from timeout.models import Post, Comment

User = get_user_model()


class DeleteCommentViewTest(TestCase):
    """Tests for the delete_comment view."""

    def setUp(self):
        """Create author, staff, other user, a post, and a comment."""
        self.author = User.objects.create_user(username="author", password="pass")
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True,
        )
        self.other = User.objects.create_user(username="other", password="pass")
        self.post = Post.objects.create(
            author=self.author,
            content="Post content",
            privacy=Post.Privacy.PUBLIC,
        )
        self.comment = Comment.objects.create(
            post=self.post,
            author=self.author,
            content="Author comment",
        )

    def login(self, user):
        """Log in the given user via the test client."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def delete_url(self, comment_id=None):
        """Return the delete_comment URL for the given or default comment."""
        return reverse("delete_comment", args=[comment_id or self.comment.id])

    def test_author_can_delete_own_comment(self):
        """Author deleting their comment redirects to feed and removes the comment."""
        self.login(self.author)
        response = self.client.post(self.delete_url())
        self.assertRedirects(response, reverse("social_feed"), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())
        msgs = list(get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("Comment deleted", str(msgs[0]))

    def test_staff_can_delete_any_comment(self):
        """Staff user can delete a comment they did not author."""
        self.login(self.staff)
        response = self.client.post(self.delete_url())
        self.assertRedirects(response, reverse("social_feed"), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_non_author_non_staff_gets_403(self):
        """A user who is neither the author nor staff receives a 403."""
        self.login(self.other)
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    def test_delete_comment_requires_login(self):
        """Unauthenticated delete attempt redirects to the login page."""
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_delete_comment_rejects_get(self):
        """GET request to the delete endpoint returns 405."""
        self.login(self.author)
        response = self.client.get(self.delete_url())
        self.assertEqual(response.status_code, 405)

    def test_delete_nonexistent_comment_returns_404(self):
        """Attempting to delete a comment that does not exist returns 404."""
        self.login(self.staff)
        response = self.client.post(self.delete_url(comment_id=99999))
        self.assertEqual(response.status_code, 404)


class BanUserViewTest(TestCase):
    """Tests for the ban_user view."""

    def setUp(self):
        """Create a staff user, a regular user, and another staff user."""
        self.staff = User.objects.create_user(
            username="admin", password="pass", is_staff=True,
        )
        self.regular = User.objects.create_user(username="regular", password="pass")
        self.other_staff = User.objects.create_user(
            username="otherstaff", password="pass", is_staff=True,
        )

    def login(self, user):
        """Log in the given user via the test client."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def ban_url(self, username):
        """Return the ban_user URL for the given username."""
        return reverse("ban_user", args=[username])

    def test_staff_can_ban_regular_user(self):
        """Staff banning a regular user sets is_banned, saves the reason, and shows a message."""
        self.login(self.staff)
        response = self.client.post(
            self.ban_url(self.regular.username),
            data={"reason": "Violating community guidelines"},
        )
        self.assertRedirects(
            response,
            reverse("user_profile", args=[self.regular.username]),
            fetch_redirect_response=False,
        )
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)
        self.assertEqual(self.regular.ban_reason, "Violating community guidelines")
        msgs = list(get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("has been banned", str(msgs[0]))

    def test_ban_user_empty_reason(self):
        """Banning with no reason stores an empty ban_reason."""
        self.login(self.staff)
        self.client.post(self.ban_url(self.regular.username), data={})
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)
        self.assertEqual(self.regular.ban_reason, "")

    def test_non_staff_gets_403(self):
        """A non-staff user attempting to ban receives a 403."""
        self.login(self.regular)
        response = self.client.post(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 403)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_banned)

    def test_cannot_ban_staff_member(self):
        """Attempting to ban a staff member redirects with an error message."""
        self.login(self.staff)
        response = self.client.post(self.ban_url(self.other_staff.username))
        self.assertRedirects(
            response,
            reverse("user_profile", args=[self.other_staff.username]),
            fetch_redirect_response=False,
        )
        self.other_staff.refresh_from_db()
        self.assertFalse(self.other_staff.is_banned)
        msgs = list(get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("Cannot ban a staff member", str(msgs[0]))

    def test_ban_nonexistent_user_returns_404(self):
        """Attempting to ban a user that does not exist returns 404."""
        self.login(self.staff)
        response = self.client.post(self.ban_url("nonexistent"))
        self.assertEqual(response.status_code, 404)

    def test_ban_user_requires_login(self):
        """Unauthenticated ban attempt redirects to the login page."""
        response = self.client.post(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_ban_user_rejects_get(self):
        """GET request to the ban endpoint returns 405."""
        self.login(self.staff)
        response = self.client.get(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 405)

    def test_ajax_ban_returns_json(self):
        """AJAX ban by staff returns 200 with JSON ok and sets is_banned."""
        self.login(self.staff)
        response = self.client.post(
            self.ban_url(self.regular.username),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True})
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)

    def test_ajax_non_staff_gets_403_json(self):
        """AJAX ban by non-staff returns 403 with an error key."""
        self.login(self.regular)
        response = self.client.post(
            self.ban_url(self.regular.username),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

    def test_ajax_cannot_ban_staff_returns_400_json(self):
        """AJAX attempt to ban a staff member returns 400 with an error key."""
        self.login(self.staff)
        response = self.client.post(
            self.ban_url(self.other_staff.username),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class UnbanUserViewTest(TestCase):
    """Tests for the unban_user view."""

    def setUp(self):
        """Create a staff user, a pre-banned regular user, and an other user."""
        self.staff = User.objects.create_user(
            username="admin", password="pass", is_staff=True,
        )
        self.regular = User.objects.create_user(username="regular", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        # Pre-ban the regular user
        self.regular.is_banned = True
        self.regular.ban_reason = "Spam"
        self.regular.save()

    def login(self, user):
        """Log in the given user via the test client."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def unban_url(self, username):
        """Return the unban_user URL for the given username."""
        return reverse("unban_user", args=[username])

    def test_staff_can_unban_user(self):
        """Staff unbanning a user clears is_banned, clears ban_reason, and shows a message."""
        self.login(self.staff)
        response = self.client.post(self.unban_url(self.regular.username))
        self.assertRedirects(
            response,
            reverse("user_profile", args=[self.regular.username]),
            fetch_redirect_response=False,
        )
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_banned)
        self.assertEqual(self.regular.ban_reason, "")
        msgs = list(get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("has been unbanned", str(msgs[0]))

    def test_non_staff_gets_403(self):
        """A non-staff user attempting to unban receives a 403."""
        self.login(self.other)
        response = self.client.post(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 403)
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)

    def test_unban_nonexistent_user_returns_404(self):
        """Attempting to unban a user that does not exist returns 404."""
        self.login(self.staff)
        response = self.client.post(self.unban_url("nonexistent"))
        self.assertEqual(response.status_code, 404)

    def test_unban_user_requires_login(self):
        """Unauthenticated unban attempt redirects to the login page."""
        response = self.client.post(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_unban_user_rejects_get(self):
        """GET request to the unban endpoint returns 405."""
        self.login(self.staff)
        response = self.client.get(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 405)

    def test_ajax_unban_returns_json(self):
        """AJAX unban by staff returns 200 with JSON ok and clears is_banned."""
        self.login(self.staff)
        response = self.client.post(
            self.unban_url(self.regular.username),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True})
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_banned)

    def test_ajax_non_staff_gets_403_json(self):
        """AJAX unban by non-staff returns 403 with an error key."""
        self.login(self.other)
        response = self.client.post(
            self.unban_url(self.regular.username),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())


class BannedUserMiddlewareTest(TestCase):
    """Tests for the BannedUserMiddleware."""

    def setUp(self):
        """Create a normal user and a pre-banned user."""
        self.user = User.objects.create_user(username="user", password="pass")
        self.banned_user = User.objects.create_user(username="banned", password="pass")
        self.banned_user.is_banned = True
        self.banned_user.ban_reason = "Testing ban"
        self.banned_user.save()

    def login(self, user):
        """Log in the given user via the test client."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def test_banned_user_is_logged_out_and_redirected(self):
        """Banned user is logged out and redirected to /banned/ on any page visit."""
        self.login(self.banned_user)
        response = self.client.get(reverse("social_feed"))
        self.assertRedirects(response, "/banned/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_banned_user_on_banned_page_has_no_middleware_loop(self):
        """Middleware does not redirect to /banned/ when already on /banned/."""
        self.login(self.banned_user)
        response = self.client.get("/banned/")
        if response.status_code == 302:
            self.assertNotEqual(response["Location"], "/banned/")

    def test_non_banned_user_passes_through(self):
        """A non-banned authenticated user can access pages normally."""
        self.login(self.user)
        response = self.client.get(reverse("social_feed"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

    def test_unauthenticated_user_passes_through(self):
        """An unauthenticated user is not redirected by the middleware."""
        response = self.client.get("/accounts/login/")
        self.assertNotEqual(response.status_code, 302)

    def test_middleware_calls_get_response_for_normal_user(self):
        """Middleware calls get_response and returns its result for a non-banned user."""
        factory = RequestFactory()
        request = factory.get("/some-page/")
        request.user = self.user
        request.session = self.client.session

        sentinel = object()
        middleware = BannedUserMiddleware(lambda r: sentinel)
        result = middleware(request)
        self.assertIs(result, sentinel)
