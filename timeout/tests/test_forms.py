"""
Tests for the forms in the timeout app, including SignupForm, LoginForm, and CompleteProfileForm.
These tests cover validation logic, such as password strength and similarity checks, as well as form field configurations and save behavior. 
The tests ensure that the forms behave as expected under various input conditions, including edge cases like duplicate emails and university choices. 
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from timeout.forms import SignupForm, LoginForm, CompleteProfileForm
from timeout.forms.auth import validate_password_strength, check_similarity
from django.core.exceptions import ValidationError

User = get_user_model()


class SignupFormTests(TestCase):
    """Tests for the SignupForm validation logic."""

    def _form_data(self, **overrides):
        """Return valid signup data with optional overrides."""
        data = {
            'email': 'new@example.com',
            'password1': 'Strong@Pass1',
            'password2': 'Strong@Pass1',
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        """Test that a valid form is considered valid."""
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())

    def test_save_creates_user(self):
        """Test that saving the form creates a new user."""
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.username.startswith('user_'))
        self.assertTrue(user.check_password('Strong@Pass1'))
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_save_without_commit(self):
        """Test that saving the form with commit=False does not save the user."""
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())
        user = form.save(commit=False)
        self.assertIsNone(user.pk)

    def test_password_too_short(self):
        """Test that a password that is too short is rejected."""
        form = SignupForm(data=self._form_data(password1='Ab1!', password2='Ab1!'))
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)
        self.assertIn('at least 8 characters', form.errors['password1'][0])

    def test_password_no_uppercase(self):
        """Test that a password without an uppercase letter is rejected."""
        form = SignupForm(data=self._form_data(
            password1='strong@pass1', password2='strong@pass1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('uppercase', form.errors['password1'][0])

    def test_password_no_lowercase(self):
        """Test that a password without a lowercase letter is rejected."""
        form = SignupForm(data=self._form_data(
            password1='STRONG@PASS1', password2='STRONG@PASS1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('lowercase', form.errors['password1'][0])

    def test_password_no_digit(self):
        """Test that a password without a digit is rejected."""
        form = SignupForm(data=self._form_data(
            password1='Strong@Pass', password2='Strong@Pass'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('number', form.errors['password1'][0])

    def test_password_no_symbol(self):
        """Test that a password without a symbol is rejected."""
        form = SignupForm(data=self._form_data(
            password1='StrongPass1', password2='StrongPass1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('special character', form.errors['password1'][0])

    def test_password_mismatch(self):
        """Test that mismatched passwords are rejected."""
        form = SignupForm(data=self._form_data(
            password1='Strong@Pass1', password2='Different@Pass2'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
        self.assertIn('do not match', form.errors['password2'][0])

    def test_password_similar_to_email(self):
        """Test that a password that is too similar to the email is rejected."""
        form = SignupForm(data=self._form_data(
            email='charlotte@example.com',
            password1='Charl0tte!X',
            password2='Charl0tte!X',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('too similar to your email', str(form.errors))

    def test_short_email_local_skips_similarity(self):
        """Test that if the email local part is too short, similarity check is skipped."""
        form = SignupForm(data=self._form_data(
            email='ab@example.com',
            password1='Ab@12345!',
            password2='Ab@12345!',
        ))
        self.assertTrue(form.is_valid())

    def test_duplicate_email(self):
        """Test that an email that is already taken is rejected."""
        User.objects.create_user(
            username='existing', email='taken@example.com', password='Pass1234!'
        )
        form = SignupForm(data=self._form_data(email='taken@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('already exists', form.errors['email'][0])

    def test_clean_skips_similarity_when_password1_invalid(self):
        """Test that if password1 is invalid, the similarity check is skipped to avoid multiple errors."""
        form = SignupForm(data=self._form_data(
            password1='short',
            password2='short',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)


class LoginFormTests(TestCase):
    """Tests for the LoginForm widget configuration."""

    def test_form_has_bootstrap_classes(self):
        """Test that the form fields have the 'form-control' class for Bootstrap styling."""
        form = LoginForm()
        self.assertIn('form-control', form.fields['username'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['password'].widget.attrs['class'])

    def test_form_has_placeholders(self):
        """Test that the form fields have appropriate placeholder text."""
        form = LoginForm()
        self.assertEqual(form.fields['username'].widget.attrs['placeholder'], 'Email or username')
        self.assertEqual(form.fields['password'].widget.attrs['placeholder'], 'Password')

    def test_login_form_uses_email_field(self):
        """Test that the LoginForm uses 'username' as the field name but labels it as 'Email or Username'."""
        form = LoginForm()
        self.assertEqual(form.fields['username'].label, 'Email or Username')


class CompleteProfileFormTests(TestCase):
    """Tests for the CompleteProfileForm."""

    def setUp(self):
        """Set up a user instance for testing."""
        self.user = User.objects.create_user(
            username='user_temp123', password='TestPass1!'
        )

    def test_valid_form_with_known_university(self):
        """Test that the form is valid when a known university is selected."""
        form = CompleteProfileForm(data={
            'username': 'newname',
            'first_name': 'Test',
            'last_name': 'User',
            'university_choice': 'Oxford University',
            'year_of_study': 2,
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_valid_form_with_other_university(self):
        """Test that the form is valid when 'Other' university is selected and text is provided."""
        form = CompleteProfileForm(data={
            'username': 'newname',
            'first_name': 'Test',
            'last_name': 'User',
            'university_choice': '__other__',
            'university_other': 'MIT',
            'year_of_study': 3,
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_other_university_requires_text(self):
        """Test that if 'Other' university is selected, the university_other field is required."""
        form = CompleteProfileForm(data={
            'username': 'newname',
            'university_choice': '__other__',
            'university_other': '',
            'year_of_study': 3,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('university_other', form.errors)

    def test_empty_university_choice_invalid(self):
        """Test that an empty university choice is invalid."""
        form = CompleteProfileForm(data={
            'username': 'newname',
            'university_choice': '',
            'year_of_study': 3,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('university_choice', form.errors)

    def test_empty_username_invalid(self):
        """Test that an empty username is invalid."""
        form = CompleteProfileForm(data={
            'username': '',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_duplicate_username_invalid(self):
        """Test that a duplicate username is invalid."""
        User.objects.create_user(username='taken', password='TestPass1!')
        form = CompleteProfileForm(data={
            'username': 'taken',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_same_username_valid(self):
        """Test that keeping the same username is valid."""
        form = CompleteProfileForm(data={
            'username': 'user_temp123',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_save_sets_university(self):
        """Test that saving the form sets the university field correctly based on the choice."""
        form = CompleteProfileForm(data={
            'username': 'newname',
            'first_name': 'Test',
            'last_name': 'User',
            'university_choice': 'Durham University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.university, 'Durham University')

    def test_prepopulates_known_university(self):
        """Test that if the user's university is a known option, the form prepopulates the university_choice field."""
        self.user.university = 'Oxford University'
        self.user.save()
        form = CompleteProfileForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), 'Oxford University')

    def test_prepopulates_other_university(self):
        """Test that if the user's university is not a known option, the form prepopulates university_choice as '__other__' and sets university_other."""
        self.user.university = 'Some Unknown Uni'
        self.user.save()
        form = CompleteProfileForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), '__other__')
        self.assertEqual(form.initial.get('university_other'), 'Some Unknown Uni')


class ValidatePasswordStrengthTests(TestCase):
    """Tests for validate_password_strength helper."""

    def test_valid_password(self):
        """Test that a strong password passes validation."""
        validate_password_strength('Strong@Pass1')

    def test_too_short(self):
        """Test that a password that is too short fails validation."""
        with self.assertRaises(ValidationError):
            validate_password_strength('Ab1!')

    def test_no_uppercase(self):
        """Test that a password without an uppercase letter fails validation."""
        with self.assertRaises(ValidationError):
            validate_password_strength('strong@pass1')

    def test_no_lowercase(self):
        """Test that a password without a lowercase letter fails validation."""
        with self.assertRaises(ValidationError):
            validate_password_strength('STRONG@PASS1')

    def test_no_digit(self):
        """Test that a password without a digit fails validation."""
        with self.assertRaises(ValidationError):
            validate_password_strength('Strong@Pass')

    def test_no_symbol(self):
        """Test that a password without a symbol fails validation."""
        with self.assertRaises(ValidationError):
            validate_password_strength('StrongPass1')


class CheckSimilarityTests(TestCase):
    """Tests for check_similarity helper."""

    def test_similar_raises(self):
        """Test that a password that is too similar to the reference raises a ValidationError."""
        with self.assertRaises(ValidationError):
            check_similarity('Alexander1!', 'alexander', 'username')

    def test_not_similar_passes(self):
        """Test that a password that is not similar to the reference passes validation."""
        check_similarity('Xyz@1234!', 'alexander', 'username')

    def test_short_reference_skips(self):
        """Test that a short reference string skips similarity check."""
        check_similarity('Ab@12345!', 'ab', 'email')
