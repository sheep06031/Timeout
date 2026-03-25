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
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def delete_url(self, comment_id=None):
        return reverse("delete_comment", args=[comment_id or self.comment.id])

    # Comment author can delete their own comment
    def test_author_can_delete_own_comment(self):
        self.login(self.author)
        response = self.client.post(self.delete_url())
        self.assertRedirects(response, reverse("social_feed"), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())
        msgs = list(get_messages(response.wsgi_request))
        self.assertEqual(len(msgs), 1)
        self.assertIn("Comment deleted", str(msgs[0]))

    # Staff can delete any comment regardless of authorship
    def test_staff_can_delete_any_comment(self):
        self.login(self.staff)
        response = self.client.post(self.delete_url())
        self.assertRedirects(response, reverse("social_feed"), fetch_redirect_response=False)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    # Non-author, non-staff user gets 403
    def test_non_author_non_staff_gets_403(self):
        self.login(self.other)
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    # Unauthenticated user is redirected to login
    def test_delete_comment_requires_login(self):
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_delete_comment_rejects_get(self):
        self.login(self.author)
        response = self.client.get(self.delete_url())
        self.assertEqual(response.status_code, 405)

    # Deleting a nonexistent comment returns 404
    def test_delete_nonexistent_comment_returns_404(self):
        self.login(self.staff)
        response = self.client.post(self.delete_url(comment_id=99999))
        self.assertEqual(response.status_code, 404)


class BanUserViewTest(TestCase):
    """Tests for the ban_user view."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin", password="pass", is_staff=True,
        )
        self.regular = User.objects.create_user(username="regular", password="pass")
        self.other_staff = User.objects.create_user(
            username="otherstaff", password="pass", is_staff=True,
        )

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def ban_url(self, username):
        return reverse("ban_user", args=[username])

    # Staff can ban a regular user
    def test_staff_can_ban_regular_user(self):
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

    # Ban reason is saved correctly, including empty reason
    def test_ban_user_empty_reason(self):
        self.login(self.staff)
        self.client.post(self.ban_url(self.regular.username), data={})
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)
        self.assertEqual(self.regular.ban_reason, "")

    # Non-staff user gets 403
    def test_non_staff_gets_403(self):
        self.login(self.regular)
        response = self.client.post(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 403)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_banned)

    # Cannot ban a staff member - redirects with error message
    def test_cannot_ban_staff_member(self):
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

    # Banning a nonexistent user returns 404
    def test_ban_nonexistent_user_returns_404(self):
        self.login(self.staff)
        response = self.client.post(self.ban_url("nonexistent"))
        self.assertEqual(response.status_code, 404)

    # Unauthenticated user is redirected to login
    def test_ban_user_requires_login(self):
        response = self.client.post(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_ban_user_rejects_get(self):
        self.login(self.staff)
        response = self.client.get(self.ban_url(self.regular.username))
        self.assertEqual(response.status_code, 405)


class UnbanUserViewTest(TestCase):
    """Tests for the unban_user view."""

    def setUp(self):
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
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def unban_url(self, username):
        return reverse("unban_user", args=[username])

    # Staff can unban a banned user
    def test_staff_can_unban_user(self):
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

    # Non-staff user gets 403
    def test_non_staff_gets_403(self):
        self.login(self.other)
        response = self.client.post(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 403)
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_banned)

    # Unbanning a nonexistent user returns 404
    def test_unban_nonexistent_user_returns_404(self):
        self.login(self.staff)
        response = self.client.post(self.unban_url("nonexistent"))
        self.assertEqual(response.status_code, 404)

    # Unauthenticated user is redirected to login
    def test_unban_user_requires_login(self):
        response = self.client.post(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_unban_user_rejects_get(self):
        self.login(self.staff)
        response = self.client.get(self.unban_url(self.regular.username))
        self.assertEqual(response.status_code, 405)


class BannedUserMiddlewareTest(TestCase):
    """Tests for the BannedUserMiddleware."""

    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.banned_user = User.objects.create_user(username="banned", password="pass")
        self.banned_user.is_banned = True
        self.banned_user.ban_reason = "Testing ban"
        self.banned_user.save()

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    # A banned user visiting any page should be logged out and redirected to /banned/
    def test_banned_user_is_logged_out_and_redirected(self):
        self.login(self.banned_user)
        response = self.client.get(reverse("social_feed"))
        self.assertRedirects(response, "/banned/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    # Middleware must NOT redirect the banned user when they are already on /banned/
    def test_banned_user_on_banned_page_has_no_middleware_loop(self):
        self.login(self.banned_user)
        response = self.client.get("/banned/")
        if response.status_code == 302:
            self.assertNotEqual(response["Location"], "/banned/")

    # A non-banned authenticated user should pass through normally
    def test_non_banned_user_passes_through(self):
        self.login(self.user)
        response = self.client.get(reverse("social_feed"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

    # An unauthenticated user should pass through normally
    def test_unauthenticated_user_passes_through(self):
        response = self.client.get("/accounts/login/")
        self.assertNotEqual(response.status_code, 302)

    # Middleware unit test with RequestFactory to verify the callable contract
    def test_middleware_calls_get_response_for_normal_user(self):
        factory = RequestFactory()
        request = factory.get("/some-page/")
        request.user = self.user
        request.session = self.client.session

        sentinel = object()
        middleware = BannedUserMiddleware(lambda r: sentinel)
        result = middleware(request)
        self.assertIs(result, sentinel)
