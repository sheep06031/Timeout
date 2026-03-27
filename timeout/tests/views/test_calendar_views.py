import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event

User = get_user_model()

class CalendarViewNavigationTests(TestCase):
    """Tests for calendar view navigation: month/year parsing, wrapping, and prev/next links."""

    def setUp(self):
        """Create a user, log in, and store the calendar URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.client.login(username="testuser", password="pass1234")
        self.url = reverse("calendar")

    def test_default_renders_current_month(self):
        """If no month/year are provided, the view should default to the current month and year."""
        today = timezone.now().date()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["month"], today.month)
        self.assertEqual(resp.context["year"], today.year)

    def test_explicit_month_year(self):
        """If valid month/year are provided, the view should use them."""
        resp = self.client.get(self.url, {"year": 2025, "month": 6})
        self.assertEqual(resp.context["month"], 6)
        self.assertEqual(resp.context["year"], 2025)
        self.assertEqual(resp.context["month_name"], "June")

    def test_invalid_year_month_falls_back_to_today(self):
        """If invalid month/year are provided, the view should fall back to the current month and year."""
        today = timezone.now().date()
        resp = self.client.get(self.url, {"year": "abc", "month": "xyz"})
        self.assertEqual(resp.context["year"], today.year)
        self.assertEqual(resp.context["month"], today.month)

    def test_month_below_one_wraps_to_december(self):
        """Month values below 1 should wrap to December of the previous year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 0})
        self.assertEqual(resp.context["month"], 12)
        self.assertEqual(resp.context["year"], 2024)

    def test_month_above_twelve_wraps_to_january(self):
        """Month values above 12 should wrap to January of the next year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 13})
        self.assertEqual(resp.context["month"], 1)
        self.assertEqual(resp.context["year"], 2026)

    def test_prev_next_mid_year(self):
        """Previous and next month calculations should work correctly in the middle of the year."""
        resp = self.client.get(self.url, {"year": 2025, "month": 6})
        self.assertEqual(resp.context["prev_month"], 5)
        self.assertEqual(resp.context["prev_year"], 2025)
        self.assertEqual(resp.context["next_month"], 7)
        self.assertEqual(resp.context["next_year"], 2025)

    def test_prev_next_year_boundary(self):
        """Previous and next month calculations should correctly handle year boundaries."""
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        self.assertEqual(resp.context["prev_month"], 12)
        self.assertEqual(resp.context["prev_year"], 2024)
        resp = self.client.get(self.url, {"year": 2025, "month": 12})
        self.assertEqual(resp.context["next_month"], 1)
        self.assertEqual(resp.context["next_year"], 2026)

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated users should be redirected to the login page when accessing the calendar view."""
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class CalendarViewWeeksGridTests(TestCase):
    """Tests for the calendar weeks grid context (today flag and in_month flag)."""

    def setUp(self):
        """Create a user, log in, and store the calendar URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="griduser", password="pass1234")
        self.client.login(username="griduser", password="pass1234")
        self.url = reverse("calendar")

    def test_today_flag_set_correctly(self):
        """The 'is_today' flag should be True for the cell corresponding to today's date, and False for all other cells."""
        today = timezone.now().date()
        resp = self.client.get(self.url, {"year": today.year, "month": today.month})
        today_cells = [d for week in resp.context["weeks"] for d in week if d["is_today"]]
        self.assertEqual(len(today_cells), 1)
        self.assertEqual(today_cells[0]["date"], today)

    def test_in_month_flag(self):
        """The 'in_month' flag should be True for all cells that belong to the current month, and False for cells from adjacent months."""
        resp = self.client.get(self.url, {"year": 2025, "month": 2})
        all_days = [d for week in resp.context["weeks"] for d in week]
        self.assertTrue(any(not d["in_month"] for d in all_days))


class CalendarViewRecurringEventTests(TestCase):
    """Tests for recurring event expansion in the calendar view."""

    def setUp(self):
        """Create a user, log in, and store the calendar URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="recuruser", password="pass1234")
        self.client.login(username="recuruser", password="pass1234")
        self.url = reverse("calendar")

    def _make_event(self, **kwargs):
        """Helper to create an event with some defaults that can be overridden."""
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
        """Daily recurring events should appear on every day of the month after the start date."""
        self._make_event(recurrence="daily")
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        all_days = [d for week in resp.context["weeks"] for d in week]
        self.assertGreaterEqual(sum(1 for d in all_days if d["events"]), 10)

    def test_weekly_recurrence_expands(self):
        """Weekly recurring events should appear on the same weekday each week after the start date."""
        self._make_event(recurrence="weekly")
        resp = self.client.get(self.url, {"year": 2025, "month": 3})
        all_days = [d for week in resp.context["weeks"] for d in week]
        days_with_events = [d["date"] for d in all_days if d["events"]]
        for expected_day in [3, 10, 17, 24, 31]:
            self.assertIn(date(2025, 3, expected_day), days_with_events)

    def test_monthly_recurrence_expands(self):
        """Monthly recurring events should appear on the same day each month after the start date."""
        self._make_event(
            start_datetime=timezone.make_aware(datetime(2025, 1, 31, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2025, 1, 31, 10, 0)),
            recurrence="monthly",
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 2})
        all_days = [d for week in resp.context["weeks"] for d in week]
        feb28 = next(d for d in all_days if d["date"] == date(2025, 2, 28))
        self.assertTrue(feb28["events"])

    def test_monthly_recurrence_crosses_year_boundary(self):
        """Monthly recurring events should continue to appear in subsequent months even across year boundaries."""
        self._make_event(
            title="Dec Monthly",
            start_datetime=timezone.make_aware(datetime(2024, 12, 15, 9, 0)),
            end_datetime=timezone.make_aware(datetime(2024, 12, 15, 10, 0)),
            recurrence="monthly",
        )
        resp = self.client.get(self.url, {"year": 2025, "month": 1})
        all_days = [d for week in resp.context["weeks"] for d in week]
        jan15 = next(d for d in all_days if d["date"] == date(2025, 1, 15))
        self.assertGreaterEqual(len(jan15["events"]), 1)

    def test_non_recurring_event_appears_on_start_date_only(self):
        """Events with 'none' recurrence should only appear on their start date."""
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
        march_16 = next(d for d in all_days if d["date"] == date(2025, 3, 16))
        self.assertEqual(len(march_16["events"]), 0)


