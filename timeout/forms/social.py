"""
social.py - Forms for social features in the Timeout application.
"""

from django import forms
from timeout.models import Post, Comment


class PostForm(forms.ModelForm):
    """Form for creating and editing posts."""

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = Post
        fields = ['content', 'event', 'privacy']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'What\'s on your mind?',
                'maxlength': '5000',
            }),
            'event': forms.Select(attrs={
                'class': 'form-select',
            }),
            'privacy': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'content': 'Post Content',
            'event': 'Link to Event (Optional)',
            'privacy': 'Who can see this?',
        }

    def __init__(self, *args, user=None, **kwargs):
        """Scopes the event queryset to events created by the given user."""
        super().__init__(*args, **kwargs)
        if user:
            self.fields['event'].queryset = user.created_events.all()
        self.fields['event'].empty_label = 'No event'
        self.fields['event'].required = False


class CommentForm(forms.ModelForm):
    """Form for creating comments on posts."""

    class Meta:
        """Defines the model and fields exposed by this form."""
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Write a comment...',
                'maxlength': '1000',
            }),
        }
        labels = {
            'content': '',
        }