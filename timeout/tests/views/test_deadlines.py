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
        self.client = Client()
        self.user = User.objects.create_user(username="dluser", password="pass1234")
        self.client.login(username="dluser", password="pass1234")
        self.url = reverse("deadline_list")

    # ------------------------------------------------------------------
    # Context data
    # ------------------------------------------------------------------
    @patch("timeout.services.deadline_service.timezone.now")
    def test_empty_deadlines(self, mock_now):
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

        # Overdue: end in the past
        Event.objects.create(
            creator=self.user,
            title="Overdue HW",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=3),
            end_datetime=now - timedelta(hours=1),
            is_completed=False,
        )
        # Urgent: ends within 24 hours
        Event.objects.create(
            creator=self.user,
            title="Urgent HW",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(hours=6),
            is_completed=False,
        )
        # Normal: ends in 5 days
        Event.objects.create(
            creator=self.user,
            title="Normal HW",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=5),
            is_completed=False,
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.context["total_count"], 3)
        self.assertEqual(resp.context["overdue_count"], 1)
        self.assertEqual(resp.context["urgent_count"], 1)

    @patch("timeout.services.deadline_service.timezone.now")
    def test_completed_deadlines_excluded(self, mock_now):
        """Completed deadlines should NOT appear in the list."""
        now = timezone.make_aware(datetime(2025, 4, 10, 12, 0))
        mock_now.return_value = now

        Event.objects.create(
            creator=self.user,
            title="Done",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=2),
            is_completed=True,
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["total_count"], 0)

    # ------------------------------------------------------------------
    # Auth guard
    # ------------------------------------------------------------------
    def test_unauthenticated_redirects(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class DeadlineMarkCompleteViewTests(TestCase):
    """Tests for the deadline_mark_complete AJAX endpoint."""

    def setUp(self):
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
        return reverse("deadline_mark_complete", kwargs={"event_id": event_id})

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------
    def test_mark_complete_success(self):
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_completed"])
        self.assertEqual(data["id"], self.deadline.pk)
        self.assertEqual(data["title"], "Essay")
        # Verify DB state
        self.deadline.refresh_from_db()
        self.assertTrue(self.deadline.is_completed)

    # ------------------------------------------------------------------
    # 404 – event not found / already completed / wrong user
    # ------------------------------------------------------------------
    def test_mark_complete_nonexistent_event(self):
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

    # ------------------------------------------------------------------
    # HTTP method / auth guards
    # ------------------------------------------------------------------
    def test_get_not_allowed(self):
        resp = self.client.get(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 405)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        resp = self.client.post(self._url(self.deadline.pk))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


# ======================================================================
# Filter / Sort / Type validation tests
# ======================================================================


class DeadlineListViewFilterSortTests(TestCase):
    """Test the filter/sort/type validation branches in deadline_list_view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="filterviewuser", password="pass1234")
        self.client.login(username="filterviewuser", password="pass1234")
        self.url = reverse("deadline_list")

    # -- Invalid status falls back to 'active' -----------------------
    def test_invalid_status_defaults_to_active(self):
        resp = self.client.get(self.url, {"status": "bogus"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["status_filter"], "active")

    # -- Invalid sort falls back to 'asc' ----------------------------
    def test_invalid_sort_defaults_to_asc(self):
        resp = self.client.get(self.url, {"sort": "bogus"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["sort_order"], "asc")

    # -- Invalid event_type falls back to '' -------------------------
    def test_invalid_event_type_defaults_to_empty(self):
        resp = self.client.get(self.url, {"type": "bogus_type"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["event_type"], "")

    # -- Valid filters pass through ----------------------------------
    def test_valid_completed_filter(self):
        resp = self.client.get(self.url, {"status": "completed"})
        self.assertEqual(resp.context["status_filter"], "completed")

    def test_valid_all_filter(self):
        resp = self.client.get(self.url, {"status": "all"})
        self.assertEqual(resp.context["status_filter"], "all")

    def test_valid_desc_sort(self):
        resp = self.client.get(self.url, {"sort": "desc"})
        self.assertEqual(resp.context["sort_order"], "desc")

    def test_valid_event_type(self):
        resp = self.client.get(self.url, {"type": "exam"})
        self.assertEqual(resp.context["event_type"], "exam")

    # -- Combined filters --------------------------------------------
    def test_combined_filters(self):
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

    # -- Context includes expected keys ------------------------------
    def test_context_has_all_keys(self):
        resp = self.client.get(self.url)
        for key in ('deadlines', 'total_count', 'overdue_count', 'urgent_count',
                     'completed_count', 'status_filter', 'sort_order', 'event_type',
                     'event_types'):
            self.assertIn(key, resp.context, f"Missing context key: {key}")