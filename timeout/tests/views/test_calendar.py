"""
Tests for calendar_view, event_create, apply_session_schedule, and subscribe_event views.
Covers: month navigation (Jan/Dec edge cases), all-day event forcing,
recurring event expansion (daily/weekly/monthly/yearly), validation errors,
session schedule bulk updates, and event subscription.
"""

import calendar as cal
import json
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event

User = get_user_model()


class CalendarViewNavigationTests(TestCase):
    """Test month/year navigation logic including boundary conditions."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.client.login(username="testuser", password="pass1234")
        self.url = reverse("calendar")

    # ------------------------------------------------------------------
    # Basic rendering
    # ------------------------------------------------------------------
    def test_default_renders_current_month(self):
        """No query params → current month/year used."""
        today = timezone.now().date()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["month"], today.month)
        self.assertEqual(resp.context["year"], today.year)

    def test_explicit_month_year(self):
        """Explicit ?year=2025&month=6 renders June 2025."""
        resp = self.client.get(self.url, {"year": 2025, "month": 6})
        self.assertEqual(resp.context["month"], 6)
        self.assertEqual(resp.context["year"], 2025)
        self.assertEqual(resp.context["month_name"], "June")

    # ------------------------------------------------------------------
    # Invalid / malformed query params
    # ------------------------------------------------------------------
    def test_invalid_year_month_falls_back_to_today(self):
        """Non-integer values fall back to current month/year."""
        today = timezone.now().date()
        resp = self.client.get(self.url, {"year": "abc", "month": "xyz"})
        self.assertEqual(resp.context["year"], today.year)
        self.assertEqual(resp.context["month"], today.month)

    # ------------------------------------------------------------------
    # Month < 1 → wraps to December of previous year
    # ------------------------------------------------------------------
    def test_month_below_one_wraps_to_december(self):
        """month=0 (or -1) should wrap to December of the previous year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 0})
        self.assertEqual(resp.context["month"], 12)
        self.assertEqual(resp.context["year"], 2024)

    def test_month_negative_wraps_to_december(self):
        resp = self.client.get(self.url, {"year": 2025, "month": -1})
        self.assertEqual(resp.context["month"], 12)
        self.assertEqual(resp.context["year"], 2024)

    # ------------------------------------------------------------------
    # Month > 12 → wraps to January of next year
    # ------------------------------------------------------------------
    def test_month_above_twelve_wraps_to_january(self):
        """month=13 should wrap to January of the next year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 13})
        self.assertEqual(resp.context["month"], 1)
        self.assertEqual(resp.context["year"], 2026)

    # ------------------------------------------------------------------
    # Prev / next link context values
    # ------------------------------------------------------------------
    def test_prev_next_mid_year(self):
        """For month=6 prev→5, next→7; same year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 6})
        self.assertEqual(resp.context["prev_month"], 5)
        self.assertEqual(resp.context["prev_year"], 2025)
        self.assertEqual(resp.context["next_month"], 7)
        self.assertEqual(resp.context["next_year"], 2025)

    def test_prev_link_january_wraps_to_december(self):
        """January's previous → December of prior year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        self.assertEqual(resp.context["prev_month"], 12)
        self.assertEqual(resp.context["prev_year"], 2024)

    def test_next_link_december_wraps_to_january(self):
        """December's next → January of following year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 12})
        self.assertEqual(resp.context["next_month"], 1)
        self.assertEqual(resp.context["next_year"], 2026)

    # ------------------------------------------------------------------
    # Authentication guard
    # ------------------------------------------------------------------
    def test_unauthenticated_redirects_to_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class CalendarViewWeeksGridTests(TestCase):
    """Verify the weeks grid structure and day metadata."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="griduser", password="pass1234")
        self.client.login(username="griduser", password="pass1234")
        self.url = reverse("calendar")

    def test_weeks_contain_seven_days_each(self):
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        for week in resp.context["weeks"]:
            self.assertEqual(len(week), 7)

    def test_today_flag_set_correctly(self):
        today = timezone.now().date()
        resp = self.client.get(self.url, {"year": today.year, "month": today.month})
        today_cells = [
            d for week in resp.context["weeks"] for d in week if d["is_today"]
        ]
        self.assertEqual(len(today_cells), 1)
        self.assertEqual(today_cells[0]["date"], today)

    def test_in_month_flag(self):
        """Days outside the requested month have in_month=False."""
        resp = self.client.get(self.url, {"year": 2025, "month": 2})
        all_days = [d for week in resp.context["weeks"] for d in week]
        out_of_month = [d for d in all_days if not d["in_month"]]
        # February 2025 grid will include days from Jan and/or March
        self.assertTrue(len(out_of_month) > 0)


class CalendarViewRecurringEventTests(TestCase):
    """Test expansion of daily, weekly, monthly, and yearly recurring events."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="recuruser", password="pass1234")
        self.client.login(username="recuruser", password="pass1234")
        self.url = reverse("calendar")

    def _make_event(self, **kwargs):
        defaults = dict(
            creator=self.user,
            title="Recurring",
            event_type="other",
            start_datetime=timezone.make_aware(datetime(2025, 3, 3, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2025, 3, 3, 10, 0)),
            recurrence="none",
        )
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def test_daily_recurrence_expands_within_month(self):
        self._make_event(recurrence="daily")
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        all_days = [d for week in resp.context["weeks"] for d in week]
        days_with_events = [d for d in all_days if d["events"]]
        self.assertGreaterEqual(len(days_with_events), 10)

    def test_weekly_recurrence_expands(self):
        self._make_event(
            start_datetime=timezone.make_aware(datetime(2025, 3, 3, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2025, 3, 3, 10, 0)),
            recurrence="weekly",
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        all_days = [d for week in resp.context["weeks"] for d in week]
        days_with_events = [d["date"] for d in all_days if d["events"]]
        for expected_day in [3, 10, 17, 24, 31]:
            self.assertIn(date(2025, 3, expected_day), days_with_events)

    def test_monthly_recurrence_expands(self):
        self._make_event(
            start_datetime=timezone.make_aware(datetime(2025, 1, 31, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2025, 1, 31, 10, 0)),
            recurrence="monthly",
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 2})
        all_days = [d for week in resp.context["weeks"] for d in week]
        feb28_days = [d for d in all_days if d["date"] == date(2025, 2, 28)]
        self.assertTrue(any(feb28_days[0]["events"]))

    def test_monthly_recurrence_crosses_year_boundary(self):
        ev = self._make_event(
            title="Dec Monthly",
            start_datetime=timezone.make_aware(datetime(2024, 12, 15, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2024, 12, 15, 10, 0)),
            recurrence="monthly",
        )
        self.assertEqual(Event.objects.filter(title="Dec Monthly", creator=self.user).count(), 1)

        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        self.assertEqual(resp.status_code, 200)

        all_days = [d for week in resp.context["weeks"] for d in week]
        jan15_cells = [d for d in all_days if d["date"] == date(2025, 1, 15)]
        self.assertEqual(len(jan15_cells), 1, "Jan 15 should appear exactly once in the grid")

        jan15_events = jan15_cells[0]["events"]
        self.assertGreaterEqual(
            len(jan15_events), 1,
            f"Expected recurring event on Jan 15 but got {jan15_events}. "
            f"Event recurrence={ev.recurrence}, start={ev.start_datetime}"
        )

    def test_yearly_global_event_shown_in_current_year(self):
        self._make_event(
            title="New Year Holiday",
            start_datetime=timezone.make_aware(datetime(2020, 1, 1, 0, 0)),
            end_datetime=timezone.make_aware(datetime(2020, 1, 1, 23, 59)),
            recurrence="yearly",
            is_global=True,
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        self.assertEqual(resp.status_code, 200)

    def test_non_recurring_event_appears_on_start_date_only(self):
        self._make_event(
            title="One-off",
            recurrence="none",
            start_datetime=timezone.make_aware(datetime(2025, 3, 15, 14, 0)),
            end_datetime=timezone.make_aware(datetime(2025, 3, 15, 15, 0)),
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        all_days = [d for week in resp.context["weeks"] for d in week]
        days_with_events = [d["date"] for d in all_days if d["events"]]
        self.assertIn(date(2025, 3, 15), days_with_events)
        march_16 = [d for d in all_days if d["date"] == date(2025, 3, 16)]
        self.assertEqual(len(march_16[0]["events"]), 0)

    def test_unknown_recurrence_breaks_loop(self):
        self._make_event(recurrence="biweekly")
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        self.assertEqual(resp.status_code, 200)


# ======================================================================
# event_create view tests
# ======================================================================


class EventCreateTests(TestCase):
    """Tests for the event_create POST view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass1234")
        self.client.login(username="creator", password="pass1234")
        self.url = reverse("event_create")

    # ------------------------------------------------------------------
    # Successful creation
    # ------------------------------------------------------------------
    def test_create_normal_event(self):
        resp = self.client.post(self.url, {
            "title": "Team Meeting",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T10:00",
            "visibility": "public",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertTrue(Event.objects.filter(title="Team Meeting").exists())

    def test_create_event_with_recurrence(self):
        resp = self.client.post(self.url, {
            "title": "Daily Standup",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T09:15",
            "recurrence": "daily",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        event = Event.objects.get(title="Daily Standup")
        self.assertEqual(event.recurrence, "daily")

    # ------------------------------------------------------------------
    # All-day event logic
    # ------------------------------------------------------------------
    def test_all_day_event_forces_midnight_times(self):
        resp = self.client.post(self.url, {
            "title": "Holiday",
            "event_type": "other",
            "start_datetime": "2025-04-10T14:30",
            "is_all_day": "on",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        event = Event.objects.get(title="Holiday")
        self.assertEqual(event.start_datetime.hour, 0)
        self.assertEqual(event.start_datetime.minute, 0)
        self.assertEqual(event.end_datetime.hour, 23)
        self.assertEqual(event.end_datetime.minute, 59)

    def test_all_day_event_missing_start_datetime_shows_error(self):
        resp = self.client.post(self.url, {
            "title": "Bad All-Day",
            "event_type": "other",
            "is_all_day": "on",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertFalse(Event.objects.filter(title="Bad All-Day").exists())

    # ------------------------------------------------------------------
    # Non-all-day missing times
    # ------------------------------------------------------------------
    def test_missing_start_time_non_all_day_shows_error(self):
        resp = self.client.post(self.url, {
            "title": "No Start",
            "event_type": "other",
            "end_datetime": "2025-04-10T10:00",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertFalse(Event.objects.filter(title="No Start").exists())

    def test_missing_end_time_non_all_day_shows_error(self):
        resp = self.client.post(self.url, {
            "title": "No End",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertFalse(Event.objects.filter(title="No End").exists())

    # ------------------------------------------------------------------
    # Validation error on save
    # ------------------------------------------------------------------
    def test_validation_error_shows_message(self):
        with patch.object(Event, "full_clean", side_effect=__import__("django.core.exceptions", fromlist=["ValidationError"]).ValidationError("bad")):
            resp = self.client.post(self.url, {
                "title": "Invalid",
                "event_type": "other",
                "start_datetime": "2025-04-10T09:00",
                "end_datetime": "2025-04-10T10:00",
            })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    def test_defaults_for_optional_fields(self):
        resp = self.client.post(self.url, {
            "title": "Minimal",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T10:00",
        })
        event = Event.objects.get(title="Minimal")
        self.assertEqual(event.recurrence, "none")
        self.assertEqual(event.event_type, "other")
        self.assertEqual(event.location, "")
        self.assertEqual(event.description, "")

    def test_allow_conflict_checkbox(self):
        resp = self.client.post(self.url, {
            "title": "Conflicting",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T10:00",
            "allow_conflict": "on",
        })
        event = Event.objects.get(title="Conflicting")
        self.assertTrue(event.allow_conflict)

    # ------------------------------------------------------------------
    # Auth guard
    # ------------------------------------------------------------------
    def test_unauthenticated_post_redirects(self):
        self.client.logout()
        resp = self.client.post(self.url, {"title": "nope"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_request_not_allowed(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# apply_session_schedule view tests
# ======================================================================


class ApplySessionScheduleTests(TestCase):
    """Tests for the apply_session_schedule AJAX endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="scheduser", password="pass1234")
        self.client.login(username="scheduser", password="pass1234")
        self.url = reverse("apply_session_schedule")

    def _create_session(self, title="Study", start_offset=timedelta(days=1), duration_hours=2):
        now = timezone.now()
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=now + start_offset,
            end_datetime=now + start_offset + timedelta(hours=duration_hours),
        )

    # -- Success path ------------------------------------------------
    def test_update_sessions_success(self):
        session = self._create_session()
        new_start = "2025-05-01T10:00"
        new_end = "2025-05-01T12:00"
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": session.pk, "start": new_start, "end": new_end}])
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)

    # -- Invalid JSON ------------------------------------------------
    def test_invalid_json_returns_400(self):
        resp = self.client.post(self.url, {"sessions": "not-valid-json"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    # -- Nonexistent event skipped -----------------------------------
    def test_nonexistent_event_skipped(self):
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": 99999, "start": "2025-05-01T10:00", "end": "2025-05-01T12:00"}])
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    # -- Wrong event type skipped ------------------------------------
    def test_wrong_event_type_skipped(self):
        event = Event.objects.create(
            creator=self.user,
            title="Not a session",
            event_type=Event.EventType.DEADLINE,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": event.pk, "start": "2025-05-01T10:00", "end": "2025-05-01T12:00"}])
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    # -- Missing key in session dict ---------------------------------
    def test_missing_key_skipped(self):
        session = self._create_session()
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": session.pk}])
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    # -- Empty sessions list -----------------------------------------
    def test_empty_sessions_list(self):
        resp = self.client.post(self.url, {"sessions": json.dumps([])})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    # -- Auth guards -------------------------------------------------
    def test_unauthenticated_redirects(self):
        self.client.logout()
        resp = self.client.post(self.url, {"sessions": "[]"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_not_allowed(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)


# ======================================================================
# subscribe_event view tests
# ======================================================================


class SubscribeEventTests(TestCase):
    """Tests for the subscribe_event AJAX endpoint."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username="owner", password="pass1234")
        self.subscriber = User.objects.create_user(username="subscriber", password="pass1234")
        self.client.login(username="subscriber", password="pass1234")
        now = timezone.now()
        self.public_event = Event.objects.create(
            creator=self.owner,
            title="Public Lecture",
            event_type=Event.EventType.CLASS,
            start_datetime=now + timedelta(days=1),
            end_datetime=now + timedelta(days=1, hours=2),
            visibility=Event.Visibility.PUBLIC,
        )

    def _url(self, pk):
        return reverse("subscribe_event", kwargs={"pk": pk})

    # -- Success path ------------------------------------------------
    def test_subscribe_success(self):
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertTrue(
            Event.objects.filter(creator=self.subscriber, title="Public Lecture").exists()
        )

    # -- Owner cannot subscribe to own event -------------------------
    def test_owner_cannot_subscribe(self):
        self.client.login(username="owner", password="pass1234")
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    # -- Duplicate subscription --------------------------------------
    def test_already_subscribed(self):
        self.client.post(self._url(self.public_event.pk))
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Already", resp.json()["error"])

    # -- Private event returns 404 -----------------------------------
    def test_private_event_404(self):
        private_event = Event.objects.create(
            creator=self.owner,
            title="Private Meeting",
            event_type=Event.EventType.MEETING,
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
            visibility=Event.Visibility.PRIVATE,
        )
        resp = self.client.post(self._url(private_event.pk))
        self.assertEqual(resp.status_code, 404)

    # -- Nonexistent event returns 404 -------------------------------
    def test_nonexistent_event_404(self):
        resp = self.client.post(self._url(99999))
        self.assertEqual(resp.status_code, 404)

    # -- Auth guards -------------------------------------------------
    def test_unauthenticated_redirects(self):
        self.client.logout()
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_not_allowed(self):
        resp = self.client.get(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 405)

    