from django import forms

from timeout.models import Note


class NoteForm(forms.ModelForm):
    """Form for creating and editing notes."""

    class Meta:
        model = Note
        fields = ['title', 'content', 'category', 'event', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Note title',
                'maxlength': '200',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Write your note here...',
                'maxlength': '5000',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'event': forms.Select(attrs={
                'class': 'form-select',
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['event'].queryset = user.created_events.all()
        self.fields['event'].empty_label = 'No event'
        self.fields['event'].required = False
        self.fields['due_date'].required = False
