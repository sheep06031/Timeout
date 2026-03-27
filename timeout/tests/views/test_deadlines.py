"""
Tests for deadline_list_view and deadline_mark_complete AJAX endpoint.
Covers: context counts (total, overdue, urgent), successful completion,
404 on missing deadline, authentication guards, HTTP method restrictions,
and filter/sort/type validation branches.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event

User = get_user_model()


class DeadlineListViewTests(TestCase):
    """Tests for the deadline_list_view."""

    def setUp(self):
        """Create a user, log in, and store the deadline list URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="dluser", password="pass1234")
        self.client.login(username="dluser", password="pass1234")
        self.url = reverse("deadline_list")

    def _make_deadline(self, title, start_offset, end_offset, is_completed=False, now=None):
        """Helper to create a deadline with specified offsets from 'now'."""
        now = now or timezone.now()
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=Event.EventType.DEADLINE,
            start_datetime=now + start_offset,
            end_datetime=now + end_offset,
            is_completed=is_completed,
        )


    @patch("timeout.services.deadline_service.timezone.now")
    def test_empty_deadlines(self, mock_now):
        """If there are no deadlines, counts should all be zero and no errors should occur."""
        mock_now.return_value = timezone.make_aware(datetime(2025, 4, 10, 12, 0))
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_count"], 0)
        self.assertEqual(resp.context["overdue_count"], 0)
        self.assertEqual(resp.context["urgent_count"], 0)

    @patch("timeout.services.deadline_service.timezone.now")
    def test_context_counts(self, mock_now):
        """Verify total_count, overdue_count, urgent_count are correct."""
        now = timezone.make_aware(datetime(2025, 4, 10, 12, 0))
        mock_now.return_value = now

        self._make_deadline("Overdue HW", -timedelta(days=3), -timedelta(hours=1), now=now)
        self._make_deadline("Urgent HW", -timedelta(days=1), timedelta(hours=6), now=now)
        self._make_deadline("Normal HW", -timedelta(days=1), timedelta(days=5), now=now)

        resp = self.client.get(self.url)
        self.assertEqual(resp.context["total_count"], 3)
        self.assertEqual(resp.context["overdue_count"], 1)
        self.assertEqual(resp.context["urgent_count"], 1)

    @patch("timeout.services.deadline_service.timezone.now")
    def test_completed_deadlines_excluded(self, mock_now):
        """Completed deadlines should NOT appear in the list."""
        now = timezone.make_aware(datetime(2025, 4, 10, 12, 0))
        mock_now.return_value = now
        self._make_deadline("Done", -timedelta(days=1), timedelta(days=2), is_completed=True, now=now)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["total_count"], 0)

    def test_unauthenticated_redirects(self):
        """Unauthenticated users should be redirected to the login page when accessing the deadline list view."""
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class DeadlineMarkCompleteViewTests(TestCase):
    """Tests for the deadline_mark_complete AJAX endpoint."""

    def setUp(self):
        """Create a user, log in, and create a sample deadline."""
        self.client = Client()
        self.user = User.objects.create_user(username="markuser", password="pass1234")
        self.client.login(username="markuser", password="pass1234")
        now = timezone.now()
        self.deadline = Event.objects.create(
            creator=self.user,
            title="Essay",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=2),
            is_completed=False,
        )

    def _url(self, event_id):
        """Helper to construct the URL for marking a deadline complete."""
        return reverse("deadline_mark_complete", kwargs={"event_id": event_id})

    def test_mark_complete_success(self):
        """Test that a valid POST request marks the deadline as completed and returns correct JSON."""
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_completed"])
        self.assertEqual(data["id"], self.deadline.pk)
        self.assertEqual(data["title"], "Essay")
        self.deadline.refresh_from_db()
        self.assertTrue(self.deadline.is_completed)

    def test_mark_complete_nonexistent_event(self):
        """Marking a nonexistent event should return a 404 with an error message."""
        resp = self.client.post(self._url(99999))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "Deadline not found.")

    def test_mark_complete_already_completed(self):
        """Marking an already-completed deadline returns 404."""
        self.deadline.is_completed = True
        self.deadline.save()
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 404)

    def test_mark_complete_wrong_user(self):
        """Another user cannot complete someone else's deadline."""
        other = User.objects.create_user(username="other", password="pass1234")
        self.client.login(username="other", password="pass1234")
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 404)

    def test_mark_complete_non_deadline_event(self):
        """Completing a non-deadline event type succeeds."""
        event = Event.objects.create(
            creator=self.user,
            title="Meeting",
            event_type="other",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.post(self._url(event.pk))
        self.assertEqual(resp.status_code, 200)

    def test_get_not_allowed(self):
        """GET requests should be rejected with 405 Method Not Allowed."""
        resp = self.client.get(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 405)

    def test_unauthenticated_redirects(self):
        """Unauthenticated users should be redirected to the login page when trying to mark complete."""
        self.client.logout()
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class DeadlineListViewFilterSortTests(TestCase):
    """Test the filter/sort/type validation branches in deadline_list_view."""

    def setUp(self):
        """Create a user, log in, and store the deadline list URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="filterviewuser", password="pass1234")
        self.client.login(username="filterviewuser", password="pass1234")
        self.url = reverse("deadline_list")

    def test_invalid_status_defaults_to_active(self):
        """An invalid 'status' filter should default to 'active' without error."""
        resp = self.client.get(self.url, {"status": "bogus"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["status_filter"], "active")

    def test_invalid_sort_defaults_to_asc(self):
        """An invalid 'sort' parameter should default to 'asc' without error."""
        resp = self.client.get(self.url, {"sort": "bogus"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["sort_order"], "asc")

    def test_invalid_event_type_defaults_to_empty(self):
        """An invalid 'type' parameter should default to '' without error."""
        resp = self.client.get(self.url, {"type": "bogus_type"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["event_type"], "")

    def test_valid_completed_filter(self):
        """A valid 'status=completed' filter should be accepted as-is."""
        resp = self.client.get(self.url, {"status": "completed"})
        self.assertEqual(resp.context["status_filter"], "completed")

    def test_valid_all_filter(self):
        """A valid 'status=all' filter should be accepted as-is."""
        resp = self.client.get(self.url, {"status": "all"})
        self.assertEqual(resp.context["status_filter"], "all")

    def test_valid_desc_sort(self):
        """A valid 'sort=desc' parameter should be accepted as-is."""
        resp = self.client.get(self.url, {"sort": "desc"})
        self.assertEqual(resp.context["sort_order"], "desc")

    def test_valid_event_type(self):
        """A valid 'type=exam' parameter should be accepted as-is."""
        resp = self.client.get(self.url, {"type": "exam"})
        self.assertEqual(resp.context["event_type"], "exam")

    def test_combined_filters(self):
        """Combining multiple valid filters should work and all be reflected in context."""
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title="Exam DL",
            event_type="exam",
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            is_completed=False,
        )
        Event.objects.create(
            creator=self.user, title="Deadline DL",
            event_type="deadline",
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=3),
            is_completed=False,
        )
        resp = self.client.get(self.url, {"status": "active", "sort": "desc", "type": "exam"})
        self.assertEqual(resp.status_code, 200)
        titles = [d['event'].title for d in resp.context['deadlines']]
        self.assertIn("Exam DL", titles)
        self.assertNotIn("Deadline DL", titles)

    def test_context_has_all_keys(self):
        """Verify that all expected context keys are present, even if no deadlines exist."""
        resp = self.client.get(self.url)
        for key in ('deadlines', 'total_count', 'overdue_count', 'urgent_count',
                     'completed_count', 'status_filter', 'sort_order', 'event_type',
                     'event_types'):
            self.assertIn(key, resp.context, f"Missing context key: {key}")