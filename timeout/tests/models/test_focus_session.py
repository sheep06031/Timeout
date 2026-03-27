from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from timeout.models.focus_session import FocusSession

User = get_user_model()


class FocusSessionModelTests(TestCase):

    def setUp(self):
        """Set up test user and focus session."""
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        now = timezone.now()
        self.session = FocusSession.objects.create(
            user=self.user,
            started_at=now,
            ended_at=now + timezone.timedelta(seconds=1800),
            duration_seconds=1800,
        )

    def test_str_includes_username(self):
        """Test that the string representation includes the username."""
        self.assertIn('testuser', str(self.session))

    def test_str_includes_duration(self):
        """Test that the string representation includes the duration."""
        self.assertIn('1800s', str(self.session))

    def test_ordering_most_recent_first(self):
        """Test that sessions are ordered with the most recent first."""
        now = timezone.now()
        older = FocusSession.objects.create(
            user=self.user,
            started_at=now - timezone.timedelta(days=1),
            ended_at=now - timezone.timedelta(days=1) + timezone.timedelta(seconds=600),
            duration_seconds=600,
        )
        sessions = list(FocusSession.objects.filter(user=self.user))
        self.assertEqual(sessions[0], self.session)
        self.assertEqual(sessions[1], older)

    def test_cascade_delete_on_user(self):
        """Test that sessions are deleted when the user is deleted."""
        self.user.delete()
        self.assertFalse(FocusSession.objects.filter(pk=self.session.pk).exists())

    def test_duration_seconds_stored_correctly(self):
        """Test that the duration_seconds field is stored correctly."""
        self.assertEqual(self.session.duration_seconds, 1800)
