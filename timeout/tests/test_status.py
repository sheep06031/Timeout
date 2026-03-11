import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


# Helpers

def make_user(username, password="testpass123", status=None):
    user = User.objects.create_user(username=username, password=password)
    if status:
        user.status = status
        user.save(update_fields=["status"])
    return user


# Model tests

class UserStatusModelTest(TestCase):

    def test_default_status_is_inactive(self):
        user = make_user("alice")
        self.assertEqual(user.status, User.Status.INACTIVE)

    def test_valid_status_choices(self):
        valid_values = {choice[0] for choice in User.Status.choices}
        self.assertIn("focus",    valid_values)
        self.assertIn("social",   valid_values)
        self.assertIn("inactive", valid_values)

    def test_status_can_be_set_to_focus(self):
        user = make_user("alice")
        user.status = User.Status.FOCUS
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "focus")

    def test_status_can_be_set_to_social(self):
        user = make_user("alice")
        user.status = User.Status.SOCIAL
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "social")

    def test_status_can_be_set_to_inactive(self):
        user = make_user("alice")
        user.status = User.Status.INACTIVE
        user.save(update_fields=["status"])
        user.refresh_from_db()
        self.assertEqual(user.status, "inactive")

    def test_status_persists_after_reload(self):
        user = make_user("alice", status="focus")
        user.refresh_from_db()
        self.assertEqual(user.status, "focus")


# update_status view tests

class UpdateStatusViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")

    def _post(self, status, logged_in=True):
        if logged_in:
            self.client.login(username="alice", password="testpass123")
        return self.client.post(
            reverse("update_status"),
            {"status": status},
        )

    def test_redirects_when_not_logged_in(self):
        response = self._post("focus", logged_in=False)
        self.assertIn(response.status_code, [301, 302])

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("update_status"))
        self.assertEqual(response.status_code, 405)

    def test_set_status_focus(self):
        response = self._post("focus")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "focus")

    def test_set_status_social(self):
        response = self._post("social")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "social")

    def test_set_status_inactive(self):
        response = self._post("inactive")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "inactive")

    def test_status_saved_to_database(self):
        self._post("focus")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "focus")

    def test_changing_status_multiple_times(self):
        self._post("focus")
        self._post("social")
        self._post("inactive")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "inactive")

    def test_invalid_status_returns_400(self):
        response = self._post("supercharged")
        self.assertEqual(response.status_code, 400)

    def test_empty_status_returns_400(self):
        response = self._post("")
        self.assertEqual(response.status_code, 400)

    def test_invalid_status_not_saved(self):
        self.alice.status = "social"
        self.alice.save(update_fields=["status"])

        self._post("not_a_real_status")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.status, "social")

    def test_response_is_json(self):
        response = self._post("focus")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_response_contains_status_key(self):
        response = self._post("social")
        data = json.loads(response.content)
        self.assertIn("status", data)


# Status visibility tests

class StatusVisibilityTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice", status="focus")
        self.bob = make_user("bob", status="social")

    def test_own_profile_shows_current_status_class(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "status-focus")

    def test_profile_status_choices_rendered(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "focus")
        self.assertContains(response, "social")
        self.assertContains(response, "inactive")

    def test_feed_shows_status_dot_for_post_author(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("social_feed"))
        self.assertEqual(response.status_code, 200)
