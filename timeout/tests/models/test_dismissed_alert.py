"""
test_dismissed_alert.py - Defines DismissedAlertModelTest for testing the DismissedAlert model's functionality, including creation,
uniqueness constraints, and behavior across different users.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model
from timeout.models import DismissedAlert

User = get_user_model()


class DismissedAlertModelTest(TestCase):
    """Tests for the DismissedAlert model, which tracks alerts dismissed by users."""
    def setUp(self):
        """Set up test user for dismissed alert tests."""
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_dismissed_alert(self):
        """Test creating a dismissed alert."""
        alert = DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        self.assertEqual(alert.user, self.user)
        self.assertEqual(alert.alert_key, 'workload_1_2026-03-26')
        self.assertIsNotNone(alert.dismissed_at)

    def test_unique_together(self):
        """Test that a user cannot have duplicate dismissed alerts for the same key."""
        DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        with self.assertRaises(Exception):
            DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')

    def test_different_users_same_key(self):
        """Test that different users can have the same alert key."""
        other_user = User.objects.create_user(username='otheruser', password='pass')
        DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        alert = DismissedAlert.objects.create(user=other_user, alert_key='workload_1_2026-03-26')
        self.assertEqual(alert.user, other_user)

    def test_get_or_create_idempotent(self):
        """Test that get_or_create does not create duplicates."""
        DismissedAlert.objects.get_or_create(user=self.user, alert_key='reschedule_5_missed')
        DismissedAlert.objects.get_or_create(user=self.user, alert_key='reschedule_5_missed')
        self.assertEqual(DismissedAlert.objects.filter(user=self.user).count(), 1)