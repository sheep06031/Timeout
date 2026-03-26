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
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())

    def test_save_creates_user(self):
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.username.startswith('user_'))
        self.assertTrue(user.check_password('Strong@Pass1'))
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_save_without_commit(self):
        form = SignupForm(data=self._form_data())
        self.assertTrue(form.is_valid())
        user = form.save(commit=False)
        self.assertIsNone(user.pk)

    def test_password_too_short(self):
        form = SignupForm(data=self._form_data(password1='Ab1!', password2='Ab1!'))
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)
        self.assertIn('at least 8 characters', form.errors['password1'][0])

    def test_password_no_uppercase(self):
        form = SignupForm(data=self._form_data(
            password1='strong@pass1', password2='strong@pass1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('uppercase', form.errors['password1'][0])

    def test_password_no_lowercase(self):
        form = SignupForm(data=self._form_data(
            password1='STRONG@PASS1', password2='STRONG@PASS1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('lowercase', form.errors['password1'][0])

    def test_password_no_digit(self):
        form = SignupForm(data=self._form_data(
            password1='Strong@Pass', password2='Strong@Pass'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('number', form.errors['password1'][0])

    def test_password_no_symbol(self):
        form = SignupForm(data=self._form_data(
            password1='StrongPass1', password2='StrongPass1'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('special character', form.errors['password1'][0])

    def test_password_mismatch(self):
        form = SignupForm(data=self._form_data(
            password1='Strong@Pass1', password2='Different@Pass2'
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
        self.assertIn('do not match', form.errors['password2'][0])

    def test_password_similar_to_email(self):
        form = SignupForm(data=self._form_data(
            email='charlotte@example.com',
            password1='Charl0tte!X',
            password2='Charl0tte!X',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('too similar to your email', str(form.errors))

    def test_short_email_local_skips_similarity(self):
        form = SignupForm(data=self._form_data(
            email='ab@example.com',
            password1='Ab@12345!',
            password2='Ab@12345!',
        ))
        self.assertTrue(form.is_valid())

    def test_duplicate_email(self):
        User.objects.create_user(
            username='existing', email='taken@example.com', password='Pass1234!'
        )
        form = SignupForm(data=self._form_data(email='taken@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('already exists', form.errors['email'][0])

    def test_clean_skips_similarity_when_password1_invalid(self):
        form = SignupForm(data=self._form_data(
            password1='short',
            password2='short',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)


class LoginFormTests(TestCase):
    """Tests for the LoginForm widget configuration."""

    def test_form_has_bootstrap_classes(self):
        form = LoginForm()
        self.assertIn('form-control', form.fields['username'].widget.attrs['class'])
        self.assertIn('form-control', form.fields['password'].widget.attrs['class'])

    def test_form_has_placeholders(self):
        form = LoginForm()
        self.assertEqual(form.fields['username'].widget.attrs['placeholder'], 'Email or username')
        self.assertEqual(form.fields['password'].widget.attrs['placeholder'], 'Password')

    def test_login_form_uses_email_field(self):
        form = LoginForm()
        self.assertEqual(form.fields['username'].label, 'Email or Username')


class CompleteProfileFormTests(TestCase):
    """Tests for the CompleteProfileForm."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='user_temp123', password='TestPass1!'
        )

    def test_valid_form_with_known_university(self):
        form = CompleteProfileForm(data={
            'username': 'newname',
            'first_name': 'Test',
            'last_name': 'User',
            'university_choice': 'Oxford University',
            'year_of_study': 2,
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_valid_form_with_other_university(self):
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
        form = CompleteProfileForm(data={
            'username': 'newname',
            'university_choice': '__other__',
            'university_other': '',
            'year_of_study': 3,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('university_other', form.errors)

    def test_empty_university_choice_invalid(self):
        form = CompleteProfileForm(data={
            'username': 'newname',
            'university_choice': '',
            'year_of_study': 3,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('university_choice', form.errors)

    def test_empty_username_invalid(self):
        form = CompleteProfileForm(data={
            'username': '',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_duplicate_username_invalid(self):
        User.objects.create_user(username='taken', password='TestPass1!')
        form = CompleteProfileForm(data={
            'username': 'taken',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_same_username_valid(self):
        form = CompleteProfileForm(data={
            'username': 'user_temp123',
            'university_choice': 'Oxford University',
            'year_of_study': 1,
        }, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_save_sets_university(self):
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
        self.user.university = 'Oxford University'
        self.user.save()
        form = CompleteProfileForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), 'Oxford University')

    def test_prepopulates_other_university(self):
        self.user.university = 'Some Unknown Uni'
        self.user.save()
        form = CompleteProfileForm(instance=self.user)
        self.assertEqual(form.initial.get('university_choice'), '__other__')
        self.assertEqual(form.initial.get('university_other'), 'Some Unknown Uni')


class ValidatePasswordStrengthTests(TestCase):
    """Tests for validate_password_strength helper."""

    def test_valid_password(self):
        validate_password_strength('Strong@Pass1')

    def test_too_short(self):
        with self.assertRaises(ValidationError):
            validate_password_strength('Ab1!')

    def test_no_uppercase(self):
        with self.assertRaises(ValidationError):
            validate_password_strength('strong@pass1')

    def test_no_lowercase(self):
        with self.assertRaises(ValidationError):
            validate_password_strength('STRONG@PASS1')

    def test_no_digit(self):
        with self.assertRaises(ValidationError):
            validate_password_strength('Strong@Pass')

    def test_no_symbol(self):
        with self.assertRaises(ValidationError):
            validate_password_strength('StrongPass1')


class CheckSimilarityTests(TestCase):
    """Tests for check_similarity helper."""

    def test_similar_raises(self):
        with self.assertRaises(ValidationError):
            check_similarity('Alexander1!', 'alexander', 'username')

    def test_not_similar_passes(self):
        check_similarity('Xyz@1234!', 'alexander', 'username')

    def test_short_reference_skips(self):
        check_similarity('Ab@12345!', 'ab', 'email')
