from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from timeout.models import Note, Event
from timeout.services import NoteService

User = get_user_model()


class NoteServiceTest(TestCase):
    """Tests for NoteService query methods."""

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
        self.note_lecture = Note.objects.create(
            owner=self.user,
            title='Lecture Notes',
            content='Chapter 1 summary',
            category=Note.Category.LECTURE,
        )
        self.note_todo = Note.objects.create(
            owner=self.user,
            title='Todo List',
            content='Finish assignment',
            category=Note.Category.TODO,
            event=self.event,
            is_pinned=True,
        )
        self.note_other_user = Note.objects.create(
            owner=self.other,
            title='Other User Note',
            content='Private stuff',
            category=Note.Category.PERSONAL,
        )

    #  get_user_notes 

    def test_get_user_notes_returns_only_own_notes(self):
        notes = NoteService.get_user_notes(self.user)
        self.assertEqual(notes.count(), 2)
        self.assertNotIn(self.note_other_user, notes)

    def test_get_user_notes_pinned_first(self):
        notes = list(NoteService.get_user_notes(self.user))
        self.assertEqual(notes[0], self.note_todo)

    def test_get_user_notes_anonymous_returns_empty(self):
        notes = NoteService.get_user_notes(AnonymousUser())
        self.assertEqual(notes.count(), 0)

    #  get_notes_by_category 

    def test_get_notes_by_category(self):
        notes = NoteService.get_notes_by_category(
            self.user, Note.Category.LECTURE
        )
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.note_lecture, notes)

    def test_get_notes_by_category_no_results(self):
        notes = NoteService.get_notes_by_category(
            self.user, Note.Category.PERSONAL
        )
        self.assertEqual(notes.count(), 0)

    def test_get_notes_by_category_anonymous_returns_empty(self):
        notes = NoteService.get_notes_by_category(
            AnonymousUser(), Note.Category.LECTURE
        )
        self.assertEqual(notes.count(), 0)

    # get_notes_for_event

    def test_get_notes_for_event(self):
        notes = NoteService.get_notes_for_event(
            self.user, self.event.id
        )
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.note_todo, notes)

    def test_get_notes_for_event_no_match(self):
        notes = NoteService.get_notes_for_event(self.user, 99999)
        self.assertEqual(notes.count(), 0)

    def test_get_notes_for_event_anonymous_returns_empty(self):
        notes = NoteService.get_notes_for_event(
            AnonymousUser(), self.event.id
        )
        self.assertEqual(notes.count(), 0)

    # search_notes
    def test_search_notes_by_title(self):
        notes = NoteService.search_notes(self.user, 'Lecture')
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.note_lecture, notes)

    def test_search_notes_by_content(self):
        notes = NoteService.search_notes(self.user, 'assignment')
        self.assertEqual(notes.count(), 1)
        self.assertIn(self.note_todo, notes)

    def test_search_notes_case_insensitive(self):
        notes = NoteService.search_notes(self.user, 'lecture')
        self.assertEqual(notes.count(), 1)

    def test_search_notes_no_results(self):
        notes = NoteService.search_notes(self.user, 'nonexistent')
        self.assertEqual(notes.count(), 0)

    def test_search_notes_anonymous_returns_empty(self):
        notes = NoteService.search_notes(AnonymousUser(), 'Lecture')
        self.assertEqual(notes.count(), 0)

    def test_search_does_not_return_other_users_notes(self):
        notes = NoteService.search_notes(self.user, 'Private')
        self.assertEqual(notes.count(), 0)
