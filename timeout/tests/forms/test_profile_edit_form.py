"""
test_profile_edit_form.py - Defines tests for ChangeUsernameForm and ProfileEditForm, covering validation rules for username changes,
university selection logic, and form initialization behavior.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model

from timeout.forms.profileEditForm import (
    ChangeUsernameForm,
    ProfileEditForm,
)

User = get_user_model()


class ChangeUsernameFormTest(TestCase):
    """Tests for ChangeUsernameForm validation rules and edge cases."""

    def setUp(self):
        """Set up a user for testing."""
        self.user = User.objects.create_user(username='existinguser', password='pass123')

    def test_valid_username(self):
        """A valid new username that is not taken and meets criteria should be accepted."""
        form = ChangeUsernameForm(data={'new_username': 'newuser'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_same_username_as_current_is_invalid(self):
        """Changing to the same username as the current one is invalid."""
        form = ChangeUsernameForm(data={'new_username': 'existinguser'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    def test_taken_username_is_invalid(self):
        """Username already taken by another user raises error."""
        User.objects.create_user(username='takenuser', password='pass123')
        form = ChangeUsernameForm(data={'new_username': 'takenuser'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    def test_username_with_allowed_special_chars(self):
        """Usernames with allowed special chars (underscore, hyphen, dot) are valid."""
        form = ChangeUsernameForm(data={'new_username': 'user_name-1.0'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_username_with_invalid_special_chars(self):
        """Usernames with disallowed special chars (e.g. @, !) are invalid."""
        form = ChangeUsernameForm(data={'new_username': 'user@name!'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    def test_username_too_short(self):
        """Usernames shorter than 3 characters are invalid."""
        form = ChangeUsernameForm(data={'new_username': 'ab'}, user=self.user)
        self.assertFalse(form.is_valid())

    def test_username_too_long(self):
        """Usernames longer than 150 characters are invalid."""
        form = ChangeUsernameForm(data={'new_username': 'a' * 151}, user=self.user)
        self.assertFalse(form.is_valid())

    def test_whitespace_is_stripped(self):
        """Leading/trailing whitespace is stripped before validation."""
        form = ChangeUsernameForm(data={'new_username': '  newuser  '}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['new_username'], 'newuser')

    def test_no_user_does_not_crash(self):
        """Form initialization without a user does not raise an error."""
        form = ChangeUsernameForm(data={'new_username': 'someuser'}, user=None)
        self.assertTrue(form.is_valid(), form.errors)

    def test_own_pk_excluded_from_duplicate_check(self):
        """Duplicate check excludes the current user's own pk."""
        # User changes to a completely different username — should pass
        form = ChangeUsernameForm(data={'new_username': 'brandnew'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)


class ProfileEditFormTest(TestCase):
    """Tests for ProfileEditForm validation and university field handling."""

    def setUp(self):
        """Set up a user for testing."""
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def _base_data(self, **overrides):
        """Helper to generate base form data with optional overrides."""
        data = {
            'first_name': '',
            'last_name': '',
            'bio': '',
            'year_of_study': '',
            'academic_interests': '',
            'management_style': 'early_bird',
            'privacy_private': False,
            'university_choice': '',
            'university_other': '',
        }
        data.update(overrides)
        return data

    def test_form_valid_minimal(self):
        """Form is valid with minimal data (all optional fields empty)."""
        form = ProfileEditForm(data=self._base_data(), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_known_university_saved(self):
        """Selecting a known university saves it correctly."""
        form = ProfileEditForm(
            data=self._base_data(university_choice='University College London'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['university'], 'University College London')

    def test_other_university_without_text_is_invalid(self):
        """Selecting "Other" without entering a name raises an error."""
        form = ProfileEditForm(
            data=self._base_data(university_choice='__other__', university_other=''),
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('university_other', form.errors)

    def test_other_university_with_text_is_valid(self):
        """Selecting "Other" with a name saves that name."""
        form = ProfileEditForm(
            data=self._base_data(university_choice='__other__', university_other='My Custom Uni'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['university'], 'My Custom Uni')

    def test_blank_university_choice_leaves_no_university_key(self):
        """Leaving the university choice blank results in no university key."""
        form = ProfileEditForm(
            data=self._base_data(university_choice=''),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('university', form.cleaned_data)

    def test_save_writes_university_to_instance(self):
        """save() writes the resolved university back to the instance."""
        form = ProfileEditForm(
            data=self._base_data(university_choice='Oxford University'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.university, 'Oxford University')

    def test_save_commit_false_does_not_hit_db(self):
        """save(commit=False) does not persist to the database."""
        form = ProfileEditForm(
            data=self._base_data(university_choice='Cambridge University'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        unsaved = form.save(commit=False)
        self.assertEqual(unsaved.university, 'Cambridge University')
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.university, 'Cambridge University')

    def test_init_preselects_known_university(self):
        """__init__ sets choice to the known university if it matches."""
        self.user.university = 'University of Manchester'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), 'University of Manchester')

    def test_init_preselects_other_for_unknown_university(self):
        """__init__ sets choice to __other__ for an unknown university."""
        self.user.university = 'Some Unknown University'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), '__other__')
        self.assertEqual(form.initial.get('university_other'), 'Some Unknown University')

    def test_init_no_university_for_new_instance(self):
        """__init__ skips pre-population for a new (unsaved) user."""
        new_user = User(username='fresh')
        form = ProfileEditForm(instance=new_user)
        self.assertNotIn('university_choice', form.initial)
