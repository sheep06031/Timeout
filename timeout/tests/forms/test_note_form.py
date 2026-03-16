from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.forms import NoteForm
from timeout.models import Note, Event

User = get_user_model()


class NoteFormTest(TestCase):
    """Tests for NoteForm validation and queryset filtering."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='user', password='pass123'
        )
        self.other = User.objects.create_user(
            username='other', password='pass123'
        )
        self.event = Event.objects.create(
            creator=self.user,
            title='Exam',
            event_type=Event.EventType.EXAM,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
        )
        self.other_event = Event.objects.create(
            creator=self.other,
            title='Other Exam',
            event_type=Event.EventType.EXAM,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
        )

    def test_valid_minimal_data(self):
        form = NoteForm(data={
            'title': 'Test Note',
            'content': 'Some content',
            'category': Note.Category.LECTURE,
        }, user=self.user)
        self.assertTrue(form.is_valid())

    def test_event_field_optional(self):
        form = NoteForm(data={
            'title': 'Test Note',
            'content': 'Content',
            'category': Note.Category.OTHER,
            'event': '',
        }, user=self.user)
        self.assertTrue(form.is_valid())

    def test_event_queryset_filtered_to_user(self):
        form = NoteForm(user=self.user)
        event_qs = form.fields['event'].queryset
        self.assertIn(self.event, event_qs)
        self.assertNotIn(self.other_event, event_qs)

    def test_init_without_user_does_not_crash(self):
        form = NoteForm(data={
            'title': 'Note',
            'content': 'Content',
            'category': Note.Category.OTHER,
        })
        self.assertIsNotNone(form)

    def test_missing_title_invalid(self):
        form = NoteForm(data={
            'title': '',
            'content': 'Content',
            'category': Note.Category.OTHER,
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_empty_content_valid(self):
        """Content is optional — notes are created empty and filled via the editor."""
        form = NoteForm(data={
            'title': 'Title',
            'content': '',
            'category': Note.Category.OTHER,
        }, user=self.user)
        self.assertTrue(form.is_valid())

    def test_invalid_category_rejected(self):
        form = NoteForm(data={
            'title': 'Note',
            'content': 'Content',
            'category': 'nonexistent',
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('category', form.errors)
