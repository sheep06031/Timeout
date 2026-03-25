from django import forms
from timeout.models import Note

class NoteForm(forms.ModelForm):
    """Form for creating and editing notes."""

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = Note
        fields = ['title', 'content', 'category', 'event', 'page_mode']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Note title',
                'maxlength': '200',
            }),
            'content': forms.HiddenInput(attrs={
                'id': 'id_content',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'event': forms.Select(attrs={
                'class': 'form-select',
            }),
            'page_mode': forms.HiddenInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Scopes the event queryset to events created by the given user."""
        super().__init__(*args, **kwargs)
        if user:
            self.fields['event'].queryset = user.created_events.all()
        self.fields['event'].empty_label = 'No event'
        self.fields['event'].required = False
        self.fields['content'].required = False
        self.fields['page_mode'].required = False