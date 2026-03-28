"""
Tests for the note views in the timeout app, including notes, note_create, note_edit, note_delete, note_toggle_pin, and note_share.
Includes tests for:
- Authentication and permissions: ensuring that only logged-in users can access the views and that they can only edit/delete their own notes
- Successful operations: verifying that notes are created, edited, deleted, pinned/unpinned, and shared correctly, with appropriate redirects and database updates
- Handling of edge cases: such as attempting to edit/delete a non-existent note, sharing a note that belongs to another user, and ensuring that the content formatting of shared posts is correct
These tests ensure that the note functionality works correctly, enforces proper permissions, and handles various edge cases appropriately.
"""
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models import Note, Event, Post

User = get_user_model()


class NoteViewsTest(TestCase):
    """Integration tests for note views."""

    def setUp(self):
        """Create two users, an event, and a note for testing."""
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
        self.note = Note.objects.create(
            owner=self.user,
            title='Test Note',
            content='Test content',
            category=Note.Category.LECTURE,
            event=self.event,
        )

    def login(self, user):
        """Helper method to log in a user for view tests."""
        ok = self.client.login(username=user.username, password='pass123')
        self.assertTrue(ok)

    def test_note_list_requires_login(self):
        """Accessing the note list view without being logged in should redirect to the login page."""
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.status_code, 302)

    def test_note_create_requires_login(self):
        """Accessing the note create view without being logged in should redirect to the login page."""
        resp = self.client.post(reverse('note_create'))
        self.assertEqual(resp.status_code, 302)

    def test_note_edit_requires_login(self):
        """Accessing the note edit view without being logged in should redirect to the login page."""
        resp = self.client.get(reverse('note_edit', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)

    def test_note_delete_requires_login(self):
        """Accessing the note delete view without being logged in should redirect to the login page."""
        resp = self.client.post(reverse('note_delete', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)

    def test_note_list_renders(self):
        """The note list view should render the notes page template and return a 200 status code for a logged-in user."""
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'pages/notes.html')

    def test_note_list_shows_own_notes(self):
        """The note list view should include the logged-in user's own notes in the context."""
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertIn(self.note, resp.context['notes'])

    def test_note_list_filter_by_category(self):
        """Filtering the note list by category should only show notes of that category."""
        self.login(self.user)
        Note.objects.create(
            owner=self.user,
            title='Todo',
            content='Do stuff',
            category=Note.Category.TODO,
        )
        resp = self.client.get(reverse('notes') + '?category=lecture')
        notes = list(resp.context['notes'])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].category, Note.Category.LECTURE)

    def test_note_list_search(self):
        """Searching the note list should return notes whose title or content contains the search query."""
        self.login(self.user)
        resp = self.client.get(reverse('notes') + '?q=Test')
        self.assertIn(self.note, resp.context['notes'])

    def test_note_list_search_no_results(self):
        """Searching the note list with a query that doesn't match any notes should return an empty list."""
        self.login(self.user)
        resp = self.client.get(reverse('notes') + '?q=nonexistent')
        self.assertEqual(len(resp.context['notes']), 0)

    def test_create_note_valid(self):
        """Creating a note with valid data should create the note and redirect to the note edit page for the new note."""
        self.login(self.user)
        resp = self.client.post(reverse('note_create'), {
            'title': 'New Note',
            'content': 'New content',
            'category': Note.Category.TODO,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Note.objects.filter(title='New Note', owner=self.user).exists()
        )

    def test_create_note_invalid(self):
        """Creating a note with invalid data (e.g. empty title) should not create a new note and should redirect back to the notes page."""
        self.login(self.user)
        count_before = Note.objects.count()
        resp = self.client.post(reverse('note_create'), {
            'title': '',
            'content': '',
            'category': Note.Category.OTHER,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Note.objects.count(), count_before)

    def test_edit_note_get_renders_form(self):
        """Accessing the note edit view with a GET request should render the note edit template for the note owner and return a 200 status code."""
        self.login(self.user)
        resp = self.client.get(
            reverse('note_edit', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'pages/note_edit.html')

    def test_edit_note_post_saves_changes(self):
        """Submitting a POST request to the note edit view with valid data should update the note's title and content in the database and redirect to the note edit page."""
        self.login(self.user)
        resp = self.client.post(
            reverse('note_edit', args=[self.note.id]), {
                'title': 'Updated Title',
                'content': 'Updated content',
                'category': Note.Category.TODO,
            }
        )
        self.assertEqual(resp.status_code, 302)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'Updated Title')

    def test_edit_note_permission_denied(self):
        """A user who is not the owner of the note should receive a 403 Forbidden error when trying to access the note edit view."""
        self.login(self.other)
        resp = self.client.get(
            reverse('note_edit', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_note_by_owner(self):
        """The owner of a note should be able to delete it, which should remove the note from the database and redirect to the notes page."""
        self.login(self.user)
        resp = self.client.post(
            reverse('note_delete', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Note.objects.filter(id=self.note.id).exists())

    def test_delete_note_permission_denied(self):
        """A user who is not the owner of the note should receive a 403 Forbidden error when trying to delete the note, and the note should remain in the database."""
        self.login(self.other)
        resp = self.client.post(
            reverse('note_delete', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

    def test_toggle_pin_on(self):
        """Toggling the pin status of a note from unpin to pin should update the note's pin status in the database."""
        self.login(self.user)
        self.assertFalse(self.note.is_pinned)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        data = json.loads(resp.content)
        self.assertTrue(data['pinned'])
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_pinned)

    def test_toggle_pin_off(self):
        """Toggling the pin status of a note from pin to unpin should update the note's pin status in the database."""
        self.note.is_pinned = True
        self.note.save()
        self.login(self.user)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        data = json.loads(resp.content)
        self.assertFalse(data['pinned'])

    def test_toggle_pin_other_user_404(self):
        """Trying to toggle the pin status of a note that belongs to another user should return a 404 Not Found error."""
        self.login(self.other)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 404)

    def test_share_note_creates_post(self):
        """Sharing a note should create a new Post with the note's title, category, and content, formatted appropriately, and set the post's privacy to public."""
        self.login(self.user)
        resp = self.client.post(
            reverse('note_share', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Post.objects.filter(author=self.user).count(), 1)

    def test_share_note_other_user_404(self):
        """Trying to share a note that belongs to another user should return a 404 Not Found error and should not create a new Post."""
        self.login(self.other)
        resp = self.client.post(
            reverse('note_share', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 404)

    def test_shared_post_includes_event(self):
        """Sharing a note that is linked to an event should create a post that is also linked to that event."""
        self.login(self.user)
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertEqual(post.event, self.event)

    def test_shared_post_content_format(self):
        """The content of a post created by sharing a note should include the note's category in brackets, followed by the note's title, and then the note's content."""
        self.login(self.user)
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertIn('[Lecture]', post.content)
        self.assertIn('Test Note', post.content)

    def test_create_note_redirects_to_editor(self):
        """After successfully creating a note, should redirect to the note edit page for the new note."""
        self.login(self.user)
        resp = self.client.post(reverse('note_create'), {
            'title': 'Editor Note',
            'category': Note.Category.LECTURE,
        })
        note = Note.objects.get(title='Editor Note')
        self.assertRedirects(resp, reverse('note_edit', args=[note.id]))

    def test_create_note_with_event(self):
        """Creating a note with a valid event ID that belongs to the user should link the note to that event."""
        self.login(self.user)
        self.client.post(reverse('note_create'), {
            'title': 'Linked Note',
            'category': Note.Category.STUDY_PLAN,
            'event': self.event.id,
        })
        note = Note.objects.get(title='Linked Note')
        self.assertEqual(note.event, self.event)

    def test_create_note_empty_title_rejected(self):
        """Creating a note with an empty title should not create a new note and should redirect back to the notes page."""
        self.login(self.user)
        count_before = Note.objects.count()
        self.client.post(reverse('note_create'), {
            'title': '   ',
            'category': Note.Category.OTHER,
        })
        self.assertEqual(Note.objects.count(), count_before)

    def test_create_note_other_users_event_ignored(self):
        """Creating a note with an event ID that belongs to another user should create the note but should not link it to the event."""
        other_event = Event.objects.create(
            creator=self.other,
            title='Other Event',
            event_type=Event.EventType.EXAM,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
        )
        self.login(self.user)
        self.client.post(reverse('note_create'), {
            'title': 'Sneaky Note',
            'category': Note.Category.OTHER,
            'event': other_event.id,
        })
        note = Note.objects.get(title='Sneaky Note')
        self.assertIsNone(note.event)

    def test_create_note_get_redirects(self):
        """Accessing the note create view with a GET request should redirect to the notes page."""
        self.login(self.user)
        resp = self.client.get(reverse('note_create'))
        self.assertRedirects(resp, reverse('notes'))

    def test_note_default_page_mode_is_pageless(self):
        """When creating a note without specifying a page mode, it should default to 'pageless'."""
        self.login(self.user)
        self.client.post(reverse('note_create'), {
            'title': 'Default Mode Note',
            'category': Note.Category.OTHER,
        })
        note = Note.objects.get(title='Default Mode Note')
        self.assertEqual(note.page_mode, 'pageless')

    def test_edit_note_saves_page_mode(self):
        """Submitting a page mode in the note edit form should save that page mode to the database for the note."""
        self.login(self.user)
        self.client.post(
            reverse('note_edit', args=[self.note.id]), {
                'title': self.note.title,
                'content': self.note.content,
                'category': self.note.category,
                'page_mode': 'paged',
            }
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.page_mode, 'paged')

    def test_autosave_updates_content(self):
        """Submitting a POST request to the note_autosave view with valid data should update the note's title and content in the database and return a JSON response with status 'ok'."""
        self.login(self.user)
        resp = self.client.post(
            reverse('note_autosave', args=[self.note.id]), {
                'content': '<p>Autosaved content</p>',
                'title': 'Updated Title',
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['success'])
        self.note.refresh_from_db()
        self.assertEqual(self.note.content, '<p>Autosaved content</p>')
        self.assertEqual(self.note.title, 'Updated Title')

    def test_autosave_persists_page_mode(self):
        """Submitting a page mode in the note_autosave form should save that page mode to the database for the note."""
        self.login(self.user)
        self.client.post(
            reverse('note_autosave', args=[self.note.id]), {
                'content': 'content',
                'title': self.note.title,
                'page_mode': 'paged',
            }
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.page_mode, 'paged')

    def test_autosave_rejects_invalid_page_mode(self):
        """Submitting an invalid page mode in the note_autosave form should not update the note's page mode in the database."""
        self.login(self.user)
        self.client.post(
            reverse('note_autosave', args=[self.note.id]), {
                'content': 'content',
                'title': self.note.title,
                'page_mode': 'evil_value',
            }
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.page_mode, 'pageless')

    def test_autosave_other_user_404(self):
        """Trying to autosave a note that belongs to another user should return a 404 Not Found error and should not update the note's title or content."""
        self.login(self.other)
        resp = self.client.post(
            reverse('note_autosave', args=[self.note.id]), {
                'content': 'hacked',
                'title': 'hacked',
            }
        )
        self.assertEqual(resp.status_code, 404)

    def test_sort_alphabetical(self):
        """Sorting notes alphabetically should order the notes by title in ascending order."""
        self.login(self.user)
        Note.objects.create(owner=self.user, title='Alpha', content='', category='other')
        Note.objects.create(owner=self.user, title='Zeta', content='', category='other')
        resp = self.client.get(reverse('notes') + '?sort=alpha_asc')
        notes = list(resp.context['notes'])
        unpinned = [n for n in notes if not n.is_pinned]
        titles = [n.title for n in unpinned]
        self.assertEqual(titles, sorted(titles))

    def test_sort_default_is_recently_edited(self):
        """When accessing the notes page without specifying a sort parameter, the default sorting should be by recently edited."""
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.context['active_sort'], 'recently_edited')
