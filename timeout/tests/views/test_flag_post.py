"""
Tests for the flag_post view in the timeout app, which allows users to report inappropriate content by flagging posts.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from timeout.models import Post, PostFlag

User = get_user_model()


class FlagPostViewTest(TestCase):
    """Tests for the flag_post view."""

    def setUp(self):
        """Create a user, an author, and a post for testing."""
        self.user = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author,
            content="Test post content",
            privacy=Post.Privacy.PUBLIC,
        )

    def login(self, user):
        """Helper method to log in a user."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def flag_url(self):
        """Helper method to get the URL for flagging the test post."""
        return reverse("flag_post", args=[self.post.id])

    def test_flag_post_creates_flag(self):
        """A POST request to flag a post should create a PostFlag object."""
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

    def test_flag_post_duplicate_returns_info(self):
        """If the same user flags the same post again, it should not create a new flag."""
        self.login(self.user)
        PostFlag.objects.create(post=self.post, reporter=self.user, reason="spam")
        response = self.client.post(self.flag_url(), data={"reason": "harassment"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertFalse(data["created"])
        self.assertEqual(PostFlag.objects.filter(post=self.post, reporter=self.user).count(), 1)

    def test_flag_post_invalid_reason_defaults_to_other(self):
        """If the reason provided is not a valid choice, it should default to 'other'."""
        self.login(self.user)
        response = self.client.post(self.flag_url(), data={
            "reason": "totally_invalid_reason",
            "description": "bad reason",
        })
        self.assertEqual(response.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, "other")

    def test_flag_post_all_valid_reasons(self):
        """Test that all valid reason choices can be used when flagging a post."""
        self.login(self.user)
        for reason_value, _ in PostFlag.Reason.choices:
            PostFlag.objects.filter(post=self.post, reporter=self.user).delete()
            self.client.post(self.flag_url(), data={"reason": reason_value})
            flag = PostFlag.objects.get(post=self.post, reporter=self.user)
            self.assertEqual(flag.reason, reason_value)

    def test_flag_post_no_reason_defaults_to_other(self):
        """If no reason is provided, it should default to 'other'."""
        self.login(self.user)
        response = self.client.post(self.flag_url(), data={})
        self.assertEqual(response.status_code, 200)
        flag = PostFlag.objects.get(post=self.post, reporter=self.user)
        self.assertEqual(flag.reason, "other")
        self.assertEqual(flag.description, "")

    def test_flag_post_requires_login(self):
        """Flagging a post requires the user to be logged in."""
        response = self.client.post(self.flag_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_flag_post_rejects_get(self):
        """The flag_post view should reject GET requests (require POST)."""
        self.login(self.user)
        response = self.client.get(self.flag_url())
        self.assertEqual(response.status_code, 405)

    def test_flag_post_nonexistent_post_returns_404(self):
        """If the post ID does not exist, should return a 404 error."""
        self.login(self.user)
        url = reverse("flag_post", args=[99999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class PostFlagModelTest(TestCase):
    """Tests for the PostFlag model __str__ method."""

    def setUp(self):
        """Create a user, an author, and a post for testing."""
        self.user = User.objects.create_user(username="reporter", password="pass")
        self.author = User.objects.create_user(username="author", password="pass")
        self.post = Post.objects.create(
            author=self.author,
            content="Some post",
            privacy=Post.Privacy.PUBLIC,
        )

    def test_str_representation(self):
        """The string representation of a PostFlag should include the reporter, post ID, and reason."""
        flag = PostFlag.objects.create(
            post=self.post, reporter=self.user, reason="spam", description="This is spam",
        )
        expected = f"reporter flagged post {self.post.id}: spam"
        self.assertEqual(str(flag), expected)

    def test_str_with_other_reason(self):
        """If the reason is 'other', the description should be included in the string representation."""
        flag = PostFlag.objects.create(
            post=self.post, reporter=self.user, reason="other",
        )
        expected = f"reporter flagged post {self.post.id}: other"
        self.assertEqual(str(flag), expected)
