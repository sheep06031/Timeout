from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class SeedCommandTests(TestCase):
    """Tests for the 'seed' management command."""

    def _call_seed(self):
        """Helper method to call the seed command and capture its output."""
        out = StringIO()
        call_command('seed', stdout=out)
        return out.getvalue()

    def test_seed_creates_superuser(self):
        """Test that the seed command creates a superuser named 'johndoe'."""
        self._call_seed()
        self.assertTrue(User.objects.filter(username='johndoe').exists())
        johndoe = User.objects.get(username='johndoe')
        self.assertTrue(johndoe.is_superuser)
        self.assertTrue(johndoe.is_staff)

    def test_seed_creates_80_regular_users(self):
        """Test that the seed command creates 80 regular users in addition to the superuser."""
        self._call_seed()
        self.assertEqual(User.objects.count(), 81)
        self.assertEqual(User.objects.filter(is_superuser=False).count(), 80)

    def test_seed_creates_follow_relationships(self):
        """Test that the seed command creates follow relationships between users."""
        self._call_seed()
        users_with_following = User.objects.filter(following__isnull=False).distinct()
        self.assertTrue(users_with_following.exists())

    def test_seed_idempotent_superuser(self):
        """Running seed twice should not create a duplicate superuser."""
        self._call_seed()
        output = self._call_seed()
        self.assertIn('already exists', output)
        self.assertEqual(User.objects.filter(username='johndoe').count(), 1)

    def test_seed_output_messages(self):
        """Test that the seed command outputs expected messages during execution."""
        output = self._call_seed()
        self.assertIn('SEEDING DATABASE', output)
        self.assertIn('Creating superuser', output)
        self.assertIn('Done!', output)


class UnseedCommandTests(TestCase):
    """Tests for the 'unseed' management command."""

    def _seed_db(self):
        """Helper method to seed the database before testing unseed."""
        call_command('seed', stdout=StringIO())

    def test_unseed_removes_everyone_by_default(self):
        """Test that the unseed command removes all users by default."""
        self._seed_db()
        out = StringIO()
        call_command('unseed', stdout=out)

        self.assertEqual(User.objects.count(), 0)
        self.assertIn('Removed', out.getvalue())

    def test_unseed_keep_super_keeps_johndoe(self):
        """Test that the unseed command with --keep-super keeps the superuser 'johndoe'."""
        self._seed_db()
        out = StringIO()
        call_command('unseed', '--keep-super', stdout=out)

        self.assertTrue(User.objects.filter(username='johndoe').exists())
        self.assertEqual(User.objects.count(), 1)

    def test_unseed_on_empty_database(self):
        """Test that running unseed on an already empty database does not cause errors."""
        out = StringIO()
        call_command('unseed', stdout=out)
        self.assertIn('already empty', out.getvalue())

    def test_unseed_output_messages(self):
        """Test that the unseed command outputs expected messages during execution."""
        self._seed_db()
        out = StringIO()
        call_command('unseed', stdout=out)
        output = out.getvalue()
        self.assertIn('Removed', output)
        self.assertIn('Remaining users:', output)
