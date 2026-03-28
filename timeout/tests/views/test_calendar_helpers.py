"""
Tests for the calendar helper functions in the timeout app, including advance_date and event_status.
"""
from datetime import date
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from timeout.views.calendar import advance_date, event_status


class AdvanceDateTests(TestCase):
    """Tests for the advance_date helper function."""

    def test_daily(self):
        """Advancing a date with 'daily' recurrence should add one day."""
        self.assertEqual(advance_date(date(2025, 3, 15), 'daily'), date(2025, 3, 16))

    def test_weekly(self):
        """Advancing a date with 'weekly' recurrence should add seven days."""
        self.assertEqual(advance_date(date(2025, 3, 15), 'weekly'), date(2025, 3, 22))

    def test_monthly(self):
        """Advancing a date with 'monthly' recurrence should add one month, handling end-of-month correctly."""
        self.assertEqual(advance_date(date(2025, 1, 31), 'monthly'), date(2025, 2, 28))

    def test_unknown_recurrence_returns_none(self):
        """If an unknown recurrence pattern is given, advance_date should return None."""
        self.assertIsNone(advance_date(date(2025, 3, 15), 'yearly'))
        self.assertIsNone(advance_date(date(2025, 3, 15), 'biweekly'))


class EventStatusTests(TestCase):
    """Tests for the event_status helper function."""

    def test_ongoing(self):
        """An event that started in the past and ends in the future should be classified as 'Ongoing'."""
        now = timezone.now()
        self.assertEqual(event_status(now - timedelta(hours=1), now + timedelta(hours=1), now), 'Ongoing')

    def test_past(self):
        """An event that ended in the past should be classified as 'Past'."""
        now = timezone.now()
        self.assertEqual(event_status(now - timedelta(hours=2), now - timedelta(hours=1), now), 'Past')

    def test_upcoming(self):
        """An event that starts in the future should be classified as 'Upcoming'."""
        now = timezone.now()
        self.assertEqual(event_status(now + timedelta(hours=1), now + timedelta(hours=2), now), 'Upcoming')
