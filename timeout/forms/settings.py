from django import forms
from timeout.models import User


class AppearanceForm(forms.ModelForm):
    """Form for managing appearance, notification, and study preferences."""

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = User
        fields = [
            'theme', 'colorblind_mode', 'font_size',
            'notification_sounds',
            'pomo_work_minutes', 'pomo_short_break', 'pomo_long_break',
            'default_note_category', 'daily_study_reminder',
            'auto_online',
        ]
        widgets = {
            'theme': forms.RadioSelect(choices=User.Theme.choices),
            'colorblind_mode': forms.RadioSelect(choices=User.ColorblindMode.choices),
            'font_size': forms.NumberInput(attrs={
                'type': 'range', 'min': 80, 'max': 150, 'step': 5,
                'class': 'form-range',
            }),
            'notification_sounds': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pomo_work_minutes': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 10, 'max': 60,
            }),
            'pomo_short_break': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 30,
            }),
            'pomo_long_break': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 5, 'max': 60,
            }),
            'default_note_category': forms.Select(attrs={'class': 'form-select'}),
            'daily_study_reminder': forms.TimeInput(attrs={
                'type': 'time', 'class': 'form-control',
            }),
            'auto_online': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }