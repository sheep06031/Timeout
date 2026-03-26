from django.test import TestCase
from django.contrib.auth import get_user_model
from timeout.models import DismissedAlert

User = get_user_model()


class DismissedAlertModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_dismissed_alert(self):
        alert = DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        self.assertEqual(alert.user, self.user)
        self.assertEqual(alert.alert_key, 'workload_1_2026-03-26')
        self.assertIsNotNone(alert.dismissed_at)

    def test_unique_together(self):
        DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        with self.assertRaises(Exception):
            DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')

    def test_different_users_same_key(self):
        other_user = User.objects.create_user(username='otheruser', password='pass')
        DismissedAlert.objects.create(user=self.user, alert_key='workload_1_2026-03-26')
        alert = DismissedAlert.objects.create(user=other_user, alert_key='workload_1_2026-03-26')
        self.assertEqual(alert.user, other_user)

    def test_get_or_create_idempotent(self):
        DismissedAlert.objects.get_or_create(user=self.user, alert_key='reschedule_5_missed')
        DismissedAlert.objects.get_or_create(user=self.user, alert_key='reschedule_5_missed')
        self.assertEqual(DismissedAlert.objects.filter(user=self.user).count(), 1)