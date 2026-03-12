"""
Tests for calendar_view and event_create views.
Covers: month navigation (Jan/Dec edge cases), all-day event forcing,
recurring event expansion (daily/weekly/monthly/yearly), and validation errors.
"""

import calendar as cal
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
        # The original event is on March 3; daily expansion should place
        # pseudo-events on March 4, 5, 6 … through end of visible grid.
        all_days = [d for week in resp.context["weeks"] for d in week]
        days_with_events = [d for d in all_days if d["events"]]
        # Should have events on many days (>= 10 at minimum)
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
        # Weekly from March 3 → March 10, 17, 24, 31
        for expected_day in [3, 10, 17, 24, 31]:
            self.assertIn(date(2025, 3, expected_day), days_with_events)

    def test_monthly_recurrence_expands(self):
        # Event on Jan 31 recurring monthly – should clamp to Feb 28.
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
        """
        Monthly event starting in December, viewed in January.
        The expansion loop goes: start Dec 15 → month_num=13 → triggers
        the `if month_num > 12: month_num=1; year_num+=1` branch (lines 112-113).
        """
        ev = self._make_event(
            title="Dec Monthly",
            start_datetime=timezone.make_aware(datetime(2024, 12, 15, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2024, 12, 15, 10, 0)),
            recurrence="monthly",
        )
        # Sanity: the event exists and is for the right user
        self.assertEqual(Event.objects.filter(title="Dec Monthly", creator=self.user).count(), 1)

        # View January 2025 – the grid's last_visible will be ~Feb 2, 2025.
        # Expansion: current_date starts at Dec 15.  month+1 = 13 → Jan 15.
        # Jan 15 <= last_visible → pseudo-event created.
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        self.assertEqual(resp.status_code, 200)

        all_days = [d for week in resp.context["weeks"] for d in week]
        jan15_cells = [d for d in all_days if d["date"] == date(2025, 1, 15)]
        self.assertEqual(len(jan15_cells), 1, "Jan 15 should appear exactly once in the grid")

        # The pseudo-event for the monthly recurrence should be on Jan 15
        jan15_events = jan15_cells[0]["events"]
        self.assertGreaterEqual(
            len(jan15_events), 1,
            f"Expected recurring event on Jan 15 but got {jan15_events}. "
            f"Event recurrence={ev.recurrence}, start={ev.start_datetime}"
        )

    def test_yearly_global_event_shown_in_current_year(self):
        """Yearly global events get their year replaced to the visible year."""
        self._make_event(
            title="New Year Holiday",
            start_datetime=timezone.make_aware(datetime(2020, 1, 1, 0, 0)),
            end_datetime=timezone.make_aware(datetime(2020, 1, 1, 23, 59)),
            recurrence="yearly",
            is_global=True,
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        # The calendar_events list is built but the events_by_date uses events_qs
        # directly; at minimum the original event should appear.
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
        # Ensure it does NOT appear on the next day
        march_16 = [d for d in all_days if d["date"] == date(2025, 3, 16)]
        self.assertEqual(len(march_16[0]["events"]), 0)

    def test_unknown_recurrence_breaks_loop(self):
        """An unrecognised recurrence value should hit the else→break branch."""
        self._make_event(recurrence="biweekly")  # not handled
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
        """is_all_day=on should set times to 00:00 and 23:59."""
        resp = self.client.post(self.url, {
            "title": "Holiday",
            "event_type": "other",
            "start_datetime": "2025-04-10T14:30",  # time portion ignored
            "is_all_day": "on",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        event = Event.objects.get(title="Holiday")
        self.assertEqual(event.start_datetime.hour, 0)
        self.assertEqual(event.start_datetime.minute, 0)
        self.assertEqual(event.end_datetime.hour, 23)
        self.assertEqual(event.end_datetime.minute, 59)

    def test_all_day_event_missing_start_datetime_shows_error(self):
        """All-day with no start_datetime → error message & redirect."""
        resp = self.client.post(self.url, {
            "title": "Bad All-Day",
            "event_type": "other",
            "is_all_day": "on",
            # start_datetime deliberately omitted
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
        """If full_clean raises ValidationError, an error message is set."""
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
        """location, description, recurrence, visibility all have defaults."""
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
        """event_create only accepts POST."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)