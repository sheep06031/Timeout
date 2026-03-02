from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

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
    ('Galatasaray University', 'Galatasaray University'),
    ('__other__', 'Other (please specify)'),
]

_KNOWN_UNIVERSITIES = {c[0] for c in UNIVERSITY_CHOICES if c[0] not in ('', '__other__')}


class ProfileEditForm(forms.ModelForm):

    university_choice = forms.ChoiceField(
        choices=UNIVERSITY_CHOICES,
        required=False,
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
        }),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'bio', 'year_of_study', 'academic_interests', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Tell us about yourself...',
                'maxlength': '500',
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
            'academic_interests': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Machine Learning, Philosophy, Economics',
                'maxlength': '300',
            }),
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.university:
            uni = self.instance.university
            if uni in _KNOWN_UNIVERSITIES:
                self.initial.setdefault('university_choice', uni)
            else:
                self.initial.setdefault('university_choice', '__other__')
                self.initial.setdefault('university_other', uni)

    def clean(self):
        cleaned_data = super().clean()
        choice = cleaned_data.get('university_choice', '')
        if choice == '__other__':
            other = cleaned_data.get('university_other', '').strip()
            if not other:
                self.add_error('university_other', 'Please enter your university name.')
            else:
                cleaned_data['university'] = other
        elif choice:
            cleaned_data['university'] = choice
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        university = self.cleaned_data.get('university')
        if university:
            instance.university = university
        if commit:
            instance.save()
        return instance