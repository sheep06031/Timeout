from django.test import TestCase
from django.contrib.auth import get_user_model

from timeout.forms.profileEditForm import (
    ChangeUsernameForm,
    ProfileEditForm,
    UNIVERSITY_CHOICES,
    _KNOWN_UNIVERSITIES,
)

User = get_user_model()


class ChangeUsernameFormTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='existinguser', password='pass123')

    # Valid new username passes
    def test_valid_username(self):
        form = ChangeUsernameForm(data={'new_username': 'newuser'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    # Same username as current raises error
    def test_same_username_as_current_is_invalid(self):
        form = ChangeUsernameForm(data={'new_username': 'existinguser'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    # Username already taken by another user raises error
    def test_taken_username_is_invalid(self):
        User.objects.create_user(username='takenuser', password='pass123')
        form = ChangeUsernameForm(data={'new_username': 'takenuser'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    # Usernames with allowed special chars (underscore, hyphen, dot) are valid
    def test_username_with_allowed_special_chars(self):
        form = ChangeUsernameForm(data={'new_username': 'user_name-1.0'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    # Username with disallowed special chars (e.g. @, !) is invalid
    def test_username_with_invalid_special_chars(self):
        form = ChangeUsernameForm(data={'new_username': 'user@name!'}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('new_username', form.errors)

    # Username shorter than 3 chars is invalid
    def test_username_too_short(self):
        form = ChangeUsernameForm(data={'new_username': 'ab'}, user=self.user)
        self.assertFalse(form.is_valid())

    # Username longer than 150 chars is invalid
    def test_username_too_long(self):
        form = ChangeUsernameForm(data={'new_username': 'a' * 151}, user=self.user)
        self.assertFalse(form.is_valid())

    # Leading/trailing whitespace is stripped before validation
    def test_whitespace_is_stripped(self):
        form = ChangeUsernameForm(data={'new_username': '  newuser  '}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['new_username'], 'newuser')

    # Works without a user instance (e.g. anonymous check)
    def test_no_user_does_not_crash(self):
        form = ChangeUsernameForm(data={'new_username': 'someuser'}, user=None)
        self.assertTrue(form.is_valid(), form.errors)

    # Duplicate check excludes the current user's own pk
    def test_own_pk_excluded_from_duplicate_check(self):
        # User changes to a completely different username — should pass
        form = ChangeUsernameForm(data={'new_username': 'brandnew'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)


class ProfileEditFormTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')

    def _base_data(self, **overrides):
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

    # Minimal data (all optional) is valid
    def test_form_valid_minimal(self):
        form = ProfileEditForm(data=self._base_data(), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    # Selecting a known university saves it correctly
    def test_known_university_saved(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice='University College London'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['university'], 'University College London')

    # Selecting "Other" without entering a name raises an error
    def test_other_university_without_text_is_invalid(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice='__other__', university_other=''),
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('university_other', form.errors)

    # Selecting "Other" with a name saves that name
    def test_other_university_with_text_is_valid(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice='__other__', university_other='My Custom Uni'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['university'], 'My Custom Uni')

    # Blank university_choice leaves university unchanged
    def test_blank_university_choice_leaves_no_university_key(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice=''),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('university', form.cleaned_data)

    # save() writes the resolved university back to the instance
    def test_save_writes_university_to_instance(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice='Oxford University'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.university, 'Oxford University')

    # save(commit=False) does not persist to the database
    def test_save_commit_false_does_not_hit_db(self):
        form = ProfileEditForm(
            data=self._base_data(university_choice='Cambridge University'),
            instance=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        unsaved = form.save(commit=False)
        self.assertEqual(unsaved.university, 'Cambridge University')
        # Reload from DB — should still have old value
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.university, 'Cambridge University')

    # __init__ pre-populates known university into university_choice
    def test_init_preselects_known_university(self):
        self.user.university = 'University of Manchester'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), 'University of Manchester')

    # __init__ sets choice to __other__ for an unknown university
    def test_init_preselects_other_for_unknown_university(self):
        self.user.university = 'Some Unknown University'
        self.user.save()
        form = ProfileEditForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), '__other__')
        self.assertEqual(form.initial.get('university_other'), 'Some Unknown University')

    # __init__ skips pre-population for a new (unsaved) user
    def test_init_no_university_for_new_instance(self):
        new_user = User(username='fresh')
        form = ProfileEditForm(instance=new_user)
        self.assertNotIn('university_choice', form.initial)
