"""
Tests for the custom User model in the timeout app.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    """Tests for the custom User model."""

    def setUp(self):
        """Set up a test user with various field values for testing."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass1!',
            first_name='Jane',
            last_name='Smith',
            middle_name='Marie',
            bio='A short bio.',
            university='Galatasaray University',
            year_of_study=2,
            academic_interests='Computer Science, Math',
            privacy_private=True,
            management_style='night_owl',
        )

    def test_user_creation(self):
        """Test that the user is created with the correct username, email, and password."""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.check_password('TestPass1!'))

    def test_custom_fields(self):
        """Test that the custom fields (first_name, last_name, middle_name, bio, university, year_of_study, academic_interests, privacy_private, management_style) are set correctly."""
        self.assertEqual(self.user.middle_name, 'Marie')
        self.assertEqual(self.user.bio, 'A short bio.')
        self.assertEqual(self.user.university, 'Galatasaray University')
        self.assertEqual(self.user.year_of_study, 2)
        self.assertEqual(self.user.academic_interests, 'Computer Science, Math')
        self.assertTrue(self.user.privacy_private)
        self.assertEqual(self.user.management_style, 'night_owl')

    def test_profile_picture_blank(self):
        """Test that the profile picture is blank by default."""
        self.assertFalse(self.user.profile_picture)

    def test_default_privacy(self):
        """Test that the default privacy setting is False."""
        user = User.objects.create_user(username='u2', password='Pass1234!')
        self.assertFalse(user.privacy_private)

    def test_default_management_style(self):
        """Test that the default management style is 'early_bird'."""
        user = User.objects.create_user(username='u3', password='Pass1234!')
        self.assertEqual(user.management_style, 'early_bird')

    def test_optional_fields_blank(self):
        """Test that optional fields (middle_name, bio, university, year_of_study, academic_interests) are blank or None when not provided."""
        user = User.objects.create_user(username='u4', password='Pass1234!')
        self.assertEqual(user.middle_name, '')
        self.assertEqual(user.bio, '')
        self.assertEqual(user.university, '')
        self.assertIsNone(user.year_of_study)
        self.assertEqual(user.academic_interests, '')

    def test_management_style_choices(self):
        """Test that the management style choices are defined correctly."""
        choices = dict(User.ManagementStyle.choices)
        self.assertEqual(choices['early_bird'], 'Early Bird')
        self.assertEqual(choices['night_owl'], 'Night Owl')

    def test_str(self):
        """Test the string representation of the user includes the username."""
        self.assertEqual(str(self.user), 'testuser')

    def test_full_name_with_middle(self):
        """Test that the get_full_name method returns the full name including the middle name."""
        self.assertEqual(self.user.get_full_name(), 'Jane Marie Smith')

    def test_full_name_without_middle(self):
        """Test that the get_full_name method returns the full name without the middle name when it is blank."""
        self.user.middle_name = ''
        self.assertEqual(self.user.get_full_name(), 'Jane Smith')

    def test_full_name_first_only(self):
        """Test that the get_full_name method returns only the first name when last name and middle name are blank."""
        self.user.middle_name = ''
        self.user.last_name = ''
        self.assertEqual(self.user.get_full_name(), 'Jane')

    def test_full_name_empty(self):
        """Test that the get_full_name method returns an empty string when all name fields are blank."""
        user = User.objects.create_user(username='empty', password='Pass1234!')
        self.assertEqual(user.get_full_name(), '')

    def test_follow_user(self):
        """Test that a user can follow another user and that the following and followers relationships are updated correctly."""
        other = User.objects.create_user(username='other', password='Pass1234!')
        self.user.following.add(other)

        self.assertIn(other, self.user.following.all())
        self.assertIn(self.user, other.followers.all())

    def test_follow_is_asymmetric(self):
        """Test that following is asymmetric, meaning if user A follows user B, it does not imply that user B follows user A."""
        other = User.objects.create_user(username='other2', password='Pass1234!')
        self.user.following.add(other)

        self.assertNotIn(self.user, other.following.all())
        self.assertNotIn(other, self.user.followers.all())

    def test_follower_count(self):
        """Test that the follower count is accurate when multiple users follow the same user."""
        u1 = User.objects.create_user(username='f1', password='Pass1234!')
        u2 = User.objects.create_user(username='f2', password='Pass1234!')
        u1.following.add(self.user)
        u2.following.add(self.user)

        self.assertEqual(self.user.follower_count, 2)

    def test_following_count(self):
        """Test that the following count is accurate when a user follows multiple other users."""
        u1 = User.objects.create_user(username='f3', password='Pass1234!')
        u2 = User.objects.create_user(username='f4', password='Pass1234!')
        u3 = User.objects.create_user(username='f5', password='Pass1234!')
        self.user.following.add(u1, u2, u3)

        self.assertEqual(self.user.following_count, 3)

    def test_unfollow(self):
        """Test that a user can unfollow another user and that the following and followers relationships are updated correctly."""
        other = User.objects.create_user(username='unfol', password='Pass1234!')
        self.user.following.add(other)
        self.user.following.remove(other)

        self.assertEqual(self.user.following_count, 0)
        self.assertEqual(other.follower_count, 0)
