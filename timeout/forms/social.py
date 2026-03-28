"""
social.py - Forms for social features in the Timeout application.

Provides two form classes:
    PostForm
        - ModelForm based on the Post model for creating and editing posts.
        - Exposes content, event, and privacy fields.
        - Applies Bootstrap-compatible widgets for content, event, and privacy fields.
        - Scopes the event dropdown to events created by the current user and marks it as optional.
    CommentForm
        - ModelForm based on the Comment model for creating comments on posts.
        - Exposes only the content field.
        - Applies a Bootstrap-compatible textarea widget for the content field.
        - Labels the content field with an empty string for a cleaner comment form appearance.
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