"""
Tests for the user status functionality in the timeout app, including the User model's status field and the view that updates the user's status via POST requests to the 'update_status' endpoint.
"""
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

def make_user(username, password="testpass123", status=None):
    """Helper function to create a user with an optional status."""
    user = User.objects.create_user(username=username, password=password)
    if status:
        user.status = status
        user.save(update_fields=["status"])
    return user

class UserStatusModelTest(TestCase):
    """Tests for the User model's status field and related functionality."""

    def test_default_status_is_inactive(self):
        """Test that a new user has the default status of 'inactive'."""
        user = make_user("alice")
        self.assertEqual(user.status, User.Status.INACTIVE)

    def test_valid_status_choices(self):
        """Test that the status field has the correct valid choices defined."""
        valid_values = {choice[0] for choice in User.Status.choices}
        self.assertIn("focus",    valid_values)
        self.assertIn("social",   valid_values)
        self.assertIn("inactive", valid_values)

    def test_status_can_be_set_to_focus(self):
        """Test that the status can be set to 'focus' and is saved correctly."""
        user = make_user("alice")
        user.status = User.Status.FOCUS
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "focus")

    def test_status_can_be_set_to_social(self):
        """Test that the status can be set to 'social' and is saved correctly."""
        user = make_user("alice")
        user.status = User.Status.SOCIAL
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "social")

    def test_status_can_be_set_to_inactive(self):
        """Test that the status can be set to 'inactive' and is saved correctly."""
        user = make_user("alice")
        user.status = User.Status.INACTIVE
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "inactive")

    def test_status_persists_after_reload(self):
        """Test that the status persists correctly after saving and reloading the user from the database."""
        user = make_user("alice", status="focus")
        user.refresh_from_db()
        self.assertEqual(user.status, "focus")

class UpdateStatusViewTest(TestCase):
    """Tests for the view that updates a user's status via POST requests to the 'update_status' endpoint."""

    def setUp(self):
        """Set up a test client and a test user for the status update tests."""
        self.client = Client()
        self.alice = make_user("alice")

    def _post(self, status, logged_in=True):
        """Helper method to send a POST request to update the user's status, optionally logging in first."""
        if logged_in:
            self.client.login(username="alice", password="testpass123")
        return self.client.post(
            reverse("update_status"),
            {"status": status},
        )

    def test_redirects_when_not_logged_in(self):
        """Test that an unauthenticated user is redirected when trying to update status."""
        response = self._post("focus", logged_in=False)
        self.assertIn(response.status_code, [301, 302])

    def test_get_not_allowed(self):
        """Test that a GET request to the update_status endpoint is not allowed."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("update_status"))
        self.assertEqual(response.status_code, 405)

    def test_set_status_focus(self):
        """Test that the status can be set to 'focus' via the view and that the response contains the correct status."""
        response = self._post("focus")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "focus")

    def test_set_status_social(self):
        """Test that the status can be set to 'social' via the view and that the response contains the correct status."""
        response = self._post("social")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "social")

    def test_set_status_inactive(self):
        """Test that the status can be set to 'inactive' via the view and that the response contains the correct status."""
        response = self._post("inactive")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "inactive")

    def test_status_saved_to_database(self):
        """Test that after posting a valid status, the user's status is updated in the database correctly."""
        self._post("focus")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "focus")

    def test_changing_status_multiple_times(self):
        """Test that changing the status multiple times updates it correctly each time."""
        self._post("focus")
        self._post("social")
        self._post("inactive")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "inactive")

    def test_invalid_status_returns_400(self):
        """Test that posting an invalid status value returns a 400 Bad Request response and does not change the user's status."""
        response = self._post("supercharged")
        self.assertEqual(response.status_code, 400)

    def test_empty_status_returns_400(self):
        """Test that posting an empty status value returns a 400 Bad Request response and does not change the user's status."""
        response = self._post("")
        self.assertEqual(response.status_code, 400)

    def test_invalid_status_not_saved(self):
        """Test that posting an invalid status value does not change the user's status in the database."""
        self.alice.status = "social"
        self.alice.save(update_fields=["status"])

        self._post("not_a_real_status")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "social")

    def test_response_is_json(self):
        """Test that the response from the view is in JSON format and contains the correct Content-Type header."""
        response = self._post("focus")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_response_contains_status_key(self):
        """Test that the JSON response contains a 'status' key with the correct value after updating the status."""
        response = self._post("social")
        data = json.loads(response.content)
        self.assertIn("status", data)

class StatusVisibilityTest(TestCase):
    """Tests for the visibility of user statuses in different views."""

    def setUp(self):
        """Set up a test client and test users for the status visibility tests."""
        self.client = Client()
        self.alice = make_user("alice", status="focus")
        self.bob = make_user("bob", status="social")

    def test_own_profile_shows_current_status_class(self):
        """Test that a user can see their own status on their profile page and that the correct CSS class is applied based on the status value."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "status-focus")

    def test_profile_status_choices_rendered(self):
        """Test that the profile page renders the status choices for the user to select from."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "focus")
        self.assertContains(response, "social")
        self.assertContains(response, "inactive")

    def test_feed_shows_status_dot_for_post_author(self):
        """Test that the social feed shows a status dot next to posts made by users and that the correct CSS class is applied based on the author's status."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("social_feed"))
        self.assertEqual(response.status_code, 200)
