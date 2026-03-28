"""
settings.py - Forms for user settings in the Timeout application.
"""

from django import forms
from timeout.models import User


class AppearanceForm(forms.ModelForm):
    """Form for managing appearance, notification, and study preferences."""

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = User
        fields = [
            'theme', 'colorblind_mode',
            'notification_sounds',
            'pomo_work_minutes', 'pomo_short_break', 'pomo_long_break',
            'default_note_category',
            'auto_online',
        ]
        widgets = {
            'theme': forms.RadioSelect(choices=User.Theme.choices),
            'colorblind_mode': forms.RadioSelect(choices=User.ColorblindMode.choices),
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
            'auto_online': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_pomo_work_minutes(self):
        """Clamp work session to a minimum of 10 minutes."""
        value = self.cleaned_data.get('pomo_work_minutes')
        if value is None:
            return value
        return max(10, value)

    def clean_pomo_short_break(self):
        """Clamp short break to [1, work duration]."""
        value = self.cleaned_data.get('pomo_short_break')
        if value is None:
            return value
        work = self.cleaned_data.get('pomo_work_minutes') or 10
        return max(1, min(value, work))

    def clean_pomo_long_break(self):
        """Clamp long break to [1, 1.5× work duration]."""
        value = self.cleaned_data.get('pomo_long_break')
        if value is None:
            return value
        work = self.cleaned_data.get('pomo_work_minutes') or 10
        return max(1, min(value, int(work * 1.5)))