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
        ok = self.client.login(username=user.username, password='pass123')
        self.assertTrue(ok)

    #  Authentication 

    def test_note_list_requires_login(self):
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.status_code, 302)

    def test_note_create_requires_login(self):
        resp = self.client.post(reverse('note_create'))
        self.assertEqual(resp.status_code, 302)

    def test_note_edit_requires_login(self):
        resp = self.client.get(reverse('note_edit', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)

    def test_note_delete_requires_login(self):
        resp = self.client.post(reverse('note_delete', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)

    #  List View 

    def test_note_list_renders(self):
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'pages/notes.html')

    def test_note_list_shows_own_notes(self):
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertIn(self.note, resp.context['notes'])

    def test_note_list_filter_by_category(self):
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
        self.login(self.user)
        resp = self.client.get(reverse('notes') + '?q=Test')
        self.assertIn(self.note, resp.context['notes'])

    def test_note_list_search_no_results(self):
        self.login(self.user)
        resp = self.client.get(reverse('notes') + '?q=nonexistent')
        self.assertEqual(len(resp.context['notes']), 0)

    #  Create View 

    def test_create_note_valid(self):
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
        self.login(self.user)
        count_before = Note.objects.count()
        resp = self.client.post(reverse('note_create'), {
            'title': '',
            'content': '',
            'category': Note.Category.OTHER,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Note.objects.count(), count_before)

    #  Edit View 

    def test_edit_note_get_renders_form(self):
        self.login(self.user)
        resp = self.client.get(
            reverse('note_edit', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'pages/note_edit.html')

    def test_edit_note_post_saves_changes(self):
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
        self.login(self.other)
        resp = self.client.get(
            reverse('note_edit', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 403)

    #  Delete View 

    def test_delete_note_by_owner(self):
        self.login(self.user)
        resp = self.client.post(
            reverse('note_delete', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Note.objects.filter(id=self.note.id).exists())

    def test_delete_note_permission_denied(self):
        self.login(self.other)
        resp = self.client.post(
            reverse('note_delete', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

    #  Pin Toggle 

    def test_toggle_pin_on(self):
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
        self.note.is_pinned = True
        self.note.save()
        self.login(self.user)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        data = json.loads(resp.content)
        self.assertFalse(data['pinned'])

    def test_toggle_pin_other_user_404(self):
        self.login(self.other)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 404)

    #  Share 

    def test_share_note_creates_post(self):
        self.login(self.user)
        resp = self.client.post(
            reverse('note_share', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Post.objects.filter(author=self.user).count(), 1)

    def test_share_note_other_user_404(self):
        self.login(self.other)
        resp = self.client.post(
            reverse('note_share', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 404)

    def test_shared_post_includes_event(self):
        self.login(self.user)
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertEqual(post.event, self.event)

    def test_shared_post_content_format(self):
        self.login(self.user)
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertIn('[Lecture]', post.content)
        self.assertIn('Test Note', post.content)

    #  Create: redirects to editor 

    def test_create_note_redirects_to_editor(self):
        self.login(self.user)
        resp = self.client.post(reverse('note_create'), {
            'title': 'Editor Note',
            'category': Note.Category.LECTURE,
        })
        note = Note.objects.get(title='Editor Note')
        self.assertRedirects(resp, reverse('note_edit', args=[note.id]))

    def test_create_note_with_event(self):
        self.login(self.user)
        self.client.post(reverse('note_create'), {
            'title': 'Linked Note',
            'category': Note.Category.STUDY_PLAN,
            'event': self.event.id,
        })
        note = Note.objects.get(title='Linked Note')
        self.assertEqual(note.event, self.event)

    def test_create_note_empty_title_rejected(self):
        self.login(self.user)
        count_before = Note.objects.count()
        self.client.post(reverse('note_create'), {
            'title': '   ',
            'category': Note.Category.OTHER,
        })
        self.assertEqual(Note.objects.count(), count_before)

    def test_create_note_other_users_event_ignored(self):
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
        self.login(self.user)
        resp = self.client.get(reverse('note_create'))
        self.assertRedirects(resp, reverse('notes'))

    #  Page mode 

    def test_note_default_page_mode_is_pageless(self):
        self.login(self.user)
        self.client.post(reverse('note_create'), {
            'title': 'Default Mode Note',
            'category': Note.Category.OTHER,
        })
        note = Note.objects.get(title='Default Mode Note')
        self.assertEqual(note.page_mode, 'pageless')

    def test_edit_note_saves_page_mode(self):
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

    #  Autosave 

    def test_autosave_updates_content(self):
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
        self.login(self.other)
        resp = self.client.post(
            reverse('note_autosave', args=[self.note.id]), {
                'content': 'hacked',
                'title': 'hacked',
            }
        )
        self.assertEqual(resp.status_code, 404)

    #  Sorting 

    def test_sort_alphabetical(self):
        self.login(self.user)
        Note.objects.create(owner=self.user, title='Alpha', content='', category='other')
        Note.objects.create(owner=self.user, title='Zeta', content='', category='other')
        resp = self.client.get(reverse('notes') + '?sort=alpha_asc')
        notes = list(resp.context['notes'])
        unpinned = [n for n in notes if not n.is_pinned]
        titles = [n.title for n in unpinned]
        self.assertEqual(titles, sorted(titles))

    def test_sort_default_is_recently_edited(self):
        self.login(self.user)
        resp = self.client.get(reverse('notes'))
        self.assertEqual(resp.context['active_sort'], 'recently_edited')
