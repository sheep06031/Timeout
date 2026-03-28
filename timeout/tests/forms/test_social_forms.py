"""
test_social_forms.py - Defines SocialFormsTest for testing PostForm and CommentForm validation behavior.
This test case focuses on verifying that the forms validate correctly with various inputs, including edge cases for
optional fields and form initialization without a user. It does not test form rendering or specific error messages.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model

from timeout.forms import PostForm, CommentForm
from timeout.models import Post

User = get_user_model()


class SocialFormsTest(TestCase):
    """
    Coverage-focused tests for PostForm and CommentForm.

    These tests verify validation behaviour only.
    They do not test rendering or detailed error messages.
    """

    def setUp(self):
        """Set up a user for testing."""
        self.user = User.objects.create_user(
            username="user", password="pass123"
        )

    def test_post_form_valid_minimal(self):
        """Minimal valid post should pass validation."""
        form = PostForm(
            data={"content": "hi", "privacy": Post.Privacy.PUBLIC},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_post_form_event_optional_blank_ok(self):
        """Event field is optional and can be blank."""
        form = PostForm(
            data={"content": "hi", "privacy": Post.Privacy.PUBLIC, "event": ""},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_post_form_init_without_user_does_not_crash(self):
        """Form should not crash when user=None is provided."""
        form = PostForm(
            data={"content": "hi", "privacy": Post.Privacy.PUBLIC},
            user=None,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_comment_form_valid(self):
        """Valid comment content should pass validation."""
        form = CommentForm(data={"content": "nice"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_comment_form_reject_too_long(self):
        """Comment exceeding max length should fail validation."""
        form = CommentForm(data={"content": "a" * 1001})
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)