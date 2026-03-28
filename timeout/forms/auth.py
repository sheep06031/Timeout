"""
auth.py - Forms for user authentication and profile setup in the Timeout application.

Provides three form classes covering the full registration and login flow:
    SignupForm
        - Collects email and password at initial registration.
        - Enforces password strength rules and email uniqueness.
        - Generates a temporary username; final profile details are set later.
    CompleteProfileForm
        - Collects username, name, university, and year of study.
        - Supports both social and local auth users.
        - Handles the "Other" university free-text option.
    LoginForm
        - Extends Django's AuthenticationForm with Bootstrap styling.
        - Accepts either email or username as the login identifier.

Helper functions:
    validate_password_strength  - Enforces complexity rules on a raw password.
    check_similarity            - Rejects passwords too similar to a reference string.
"""

import re
import uuid
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()

def validate_password_strength(password):
    """Enforce minimum 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 symbol."""
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter.')
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter.')
    if not re.search(r'[0-9]', password):
        raise ValidationError('Password must contain at least one number.')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~/]', password):
        raise ValidationError('Password must contain at least one special character.')


def check_similarity(password, reference, label):
    """Reject passwords that share 4+ consecutive characters with reference."""
    reference_lower = reference.lower()
    password_lower = password.lower()
    for i in range(len(reference_lower) - 3):
        chunk = reference_lower[i:i + 4]
        if chunk in password_lower:
            raise ValidationError(
                f'Password is too similar to your {label}.'
            )


class SignupForm(forms.ModelForm):
    """
    Registration form: email + password only.
    Username and profile details are collected on the Complete Profile page.
    """

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password',
        }),
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
        }),
    )

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com',
            }),
        }

    def clean_email(self):
        """Rejects the email if an account with it already exists."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_password1(self):
        """Runs strength validation on the password."""
        password = self.cleaned_data.get('password1')
        validate_password_strength(password)
        return password

    def clean(self):
        """Checks passwords match and aren't too similar to the email."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        email = cleaned_data.get('email', '')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match.')

        if password1 and email:
            email_local = email.split('@')[0]
            if len(email_local) >= 4:
                check_similarity(password1, email_local, 'email')

        return cleaned_data

    def save(self, commit=True):
        """Saves the user with a hashed password and a temporary username."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.username = f'user_{uuid.uuid4().hex[:12]}'
        if commit:
            user.save()
        return user


# Universities sourced from the seed command (seed.py).
UNIVERSITY_CHOICES = [
    ('', 'Select your university'),
    ('Durham University', 'Durham University'),
    ('Imperial College London', 'Imperial College London'),
    ('Kings College London', 'Kings College London'),
    ('London Business School', 'London Business School'),
    ('London School of Economics', 'London School of Economics'),
    ('Newcastle University', 'Newcastle University'),
    ('Oxford University', 'Oxford University'),
    ('Cambridge University', 'Cambridge University'),
    ('University College London', 'University College London'),
    ('University of Bath', 'University of Bath'),
    ('University of Edinburgh', 'University of Edinburgh'),
    ('University of Glasgow', 'University of Glasgow'),
    ('University of Manchester', 'University of Manchester'),
    ('University of Warwick', 'University of Warwick'),
    ('__other__', 'Other (please specify)'),
]

# Set of known university values (for pre-population logic)
_KNOWN_UNIVERSITIES = {c[0] for c in UNIVERSITY_CHOICES if c[0] not in ('', '__other__')}


class CompleteProfileForm(forms.ModelForm):
    """
    Form for all users (local and social) to fill in the remaining
    profile fields: username, name, university, and year of study.

    University is collected via a dropdown with an optional free-text
    "Other" field that appears when the user selects the last option.
    """

    # Extra fields not in Meta (university handled via choice + other)
    university_choice = forms.ChoiceField(
        choices=UNIVERSITY_CHOICES,
        label='University',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_university_choice',
        }),
    )
    university_other = forms.CharField(
        required=False,
        label='Please specify your university',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your university name',
            'id': 'id_university_other',
            'autocomplete': 'organization',
        }),
    )

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = User
        # 'university' is intentionally excluded, resolved in clean() / save()
        fields = ['username', 'first_name', 'last_name', 'year_of_study']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username',
                'autocomplete': 'username',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
            }),
            'year_of_study': forms.Select(
                choices=[
                    ('', 'Select year'),
                    (1, '1st Year'),
                    (2, '2nd Year'),
                    (3, '3rd Year'),
                    (4, '4th Year'),
                    (5, '5th Year'),
                    (6, '6th Year'),
                    (7, 'Postgraduate'),
                ],
                attrs={'class': 'form-select'},
            ),
        }

    def __init__(self, *args, **kwargs):
        """Pre-populates university fields if the instance already has one set."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.university:
            uni = self.instance.university
            if uni in _KNOWN_UNIVERSITIES:
                self.initial.setdefault('university_choice', uni)
            else:
                self.initial.setdefault('university_choice', '__other__')
                self.initial.setdefault('university_other', uni)

    def clean_username(self):
        """Validates the username is present and not already taken."""
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('A username is required.')
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean(self):
        """Resolves the final university value from the dropdown or free-text field."""
        cleaned_data = super().clean()
        choice = cleaned_data.get('university_choice', '')

        if not choice:
            self.add_error('university_choice', 'Please select your university.')
        elif choice == '__other__':
            other = cleaned_data.get('university_other', '').strip()
            if not other:
                self.add_error('university_other', 'Please enter your university name.')
            else:
                cleaned_data['university'] = other
        else:
            cleaned_data['university'] = choice

        return cleaned_data

    def save(self, commit=True):
        """Writes the resolved university value before saving the instance."""
        instance = super().save(commit=False)
        instance.university = self.cleaned_data.get('university', '')
        if commit:
            instance.save()
        return instance


class LoginForm(AuthenticationForm):
    """Login form styled with Bootstrap classes. Authenticates via email or username."""

    username = forms.CharField(
        label='Email or Username',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email or username',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        }),
    )

    def clean(self):
        """Looks up the user by email and swaps it for their username before auth."""
        identifier = self.cleaned_data.get('username')
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if identifier and password:
            # Try email first, then fall back to username
            try:
                user = User.objects.get(email=identifier)
                self.cleaned_data['username'] = user.username
            except User.DoesNotExist:
                # Not an email — treat as username directly, let super() handle it
                pass

        return super().clean()