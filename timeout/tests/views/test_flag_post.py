import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from timeout.models import Post, PostFlag

User = get_user_model()


class FlagPostViewTest(TestCase):
    """Tests for the flag_post view."""

    def setUp(self):
        self.user = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author,
            content="Test post content",
            privacy=Post.Privacy.PUBLIC,
        )

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def flag_url(self):
        return reverse("flag_post", args=[self.post.id])

    # Successfully flag a post returns JSON with ok=True, created=True
    def test_flag_post_creates_flag(self):
        self.login(self.user)
        response = self.client.post(self.flag_url(), data={
            "reason": "spam",
            "description": "This is spam content",
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertTrue(data["created"])
        self.assertTrue(
            PostFlag.objects.filter(
                post=self.post, reporter=self.user, reason="spam",
            ).exists()
        )
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.description, "This is spam content")

    # Flagging the same post twice returns created=False, no duplicate
    def test_flag_post_duplicate_returns_info(self):
        self.login(self.user)
        PostFlag.objects.create(post=self.post, reporter=self.user, reason="spam")
        response = self.client.post(self.flag_url(), data={"reason": "harassment"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertFalse(data["created"])
        self.assertEqual(PostFlag.objects.filter(post=self.post, reporter=self.user).count(), 1)

    # An invalid reason value should default to 'other'
    def test_flag_post_invalid_reason_defaults_to_other(self):
        self.login(self.user)
        response = self.client.post(self.flag_url(), data={
            "reason": "totally_invalid_reason",
            "description": "bad reason",
        })
        self.assertEqual(response.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, "other")

    # All valid reason choices should be accepted as-is
    def test_flag_post_all_valid_reasons(self):
        self.login(self.user)
        for reason_value, _ in PostFlag.Reason.choices:
            PostFlag.objects.filter(post=self.post, reporter=self.user).delete()
            self.client.post(self.flag_url(), data={"reason": reason_value})
            flag = PostFlag.objects.get(post=self.post, reporter=self.user)
            self.assertEqual(flag.reason, reason_value)

    # Flagging without providing reason uses 'other' default
    def test_flag_post_no_reason_defaults_to_other(self):
        self.login(self.user)
        response = self.client.post(self.flag_url(), data={})
        self.assertEqual(response.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, "other")
        self.assertEqual(flag.description, "")

    # Unauthenticated user is redirected to login
    def test_flag_post_requires_login(self):
        response = self.client.post(self.flag_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # GET request should be rejected (require_POST)
    def test_flag_post_rejects_get(self):
        self.login(self.user)
        response = self.client.get(self.flag_url())
        self.assertEqual(response.status_code, 405)

    # Flagging a nonexistent post returns 404
    def test_flag_post_nonexistent_post_returns_404(self):
        self.login(self.user)
        url = reverse("flag_post", args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class PostFlagModelTest(TestCase):
    """Tests for the PostFlag model __str__ method."""

    def setUp(self):
        self.user = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author,
            content="Some post",
            privacy=Post.Privacy.PUBLIC,
        )

    def test_str_representation(self):
        flag = PostFlag.objects.create(
            post=self.post, reporter=self.user, reason="spam", description="This is spam",
        )
        expected = f"reporter flagged post {self.post.id}: spam"
        self.assertEqual(str(flag), expected)

    def test_str_with_other_reason(self):
        flag = PostFlag.objects.create(
            post=self.post, reporter=self.user, reason="other",
        )
        expected = f"reporter flagged post {self.post.id}: other"
        self.assertEqual(str(flag), expected)
