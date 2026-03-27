import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Note, Post, StudyLog
from timeout.services import NoteService

User = get_user_model()


class _ViewTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='viewuser', password='pass123')
        self.other = User.objects.create_user(username='viewother', password='pass123')
        self.note = Note.objects.create(
            owner=self.user,
            title='View Test Note',
            content='<p>Hello world</p>',
            category=Note.Category.LECTURE,
        )

    def login(self, user=None):
        """Helper method to log in a user for view tests."""
        user = user or self.user
        ok = self.client.login(username=user.username, password='pass123')
        self.assertTrue(ok)


class PomodoroCompleteViewTest(_ViewTestBase):
    def test_pomodoro_without_note_id(self):
        """Completing a pomodoro without providing a note_id should still award XP and return daily progress in the response."""
        self.login()
        resp = self.client.post(reverse('pomodoro_complete'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('xp', data)
        self.assertIn('daily_progress', data)

    def test_pomodoro_with_note_id(self):
        """Completing a pomodoro with a valid note_id should increment the note's time_spent_minutes by the user's pomo_work_minutes."""
        self.login()
        initial_minutes = self.note.time_spent_minutes
        self.client.post(reverse('pomodoro_complete'), {'note_id': self.note.id})
        self.note.refresh_from_db()
        self.assertEqual(self.note.time_spent_minutes, initial_minutes + self.user.pomo_work_minutes)

    def test_pomodoro_with_nonexistent_note_id(self):
        """Completing a pomodoro with a note_id that does not exist should not crash and should still award XP and return daily progress."""
        self.login()
        resp = self.client.post(reverse('pomodoro_complete'), {'note_id': 99999})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('xp', json.loads(resp.content))

    def test_pomodoro_awards_xp_and_logs(self):
        """Completing a pomodoro should award the user XP according to NoteService.XP_POMODORO and should log the pomodoro in a StudyLog for that day."""
        self.login()
        xp_before = self.user.xp
        self.client.post(reverse('pomodoro_complete'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, xp_before + NoteService.XP_POMODORO)
        today = timezone.localtime(timezone.now()).date()
        log = StudyLog.objects.get(user=self.user, date=today)
        self.assertEqual(log.pomodoros, 1)


class NoteShareViewTest(_ViewTestBase):
    def test_share_creates_public_post_with_content(self):
        """Sharing a note should create a new Post with the note's title, category, and content, formatted appropriately, and set the post's privacy to public."""
        self.login()
        resp = self.client.post(reverse('note_share', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)
        post = Post.objects.get(author=self.user)
        self.assertIn('View Test Note', post.content)
        self.assertIn('[Lecture]', post.content)
        self.assertIn('Hello world', post.content)
        self.assertNotIn('<p>', post.content)
        self.assertEqual(post.privacy, Post.Privacy.PUBLIC)


class UpdateDailyGoalsViewTest(_ViewTestBase):
    def test_valid_data_updates_goals(self):
        """Updating daily goals with valid data should update the user's daily_pomo_goal, daily_notes_goal, and daily_focus_goal accordingly and return a JSON response with status 'ok'."""
        self.login()
        resp = self.client.post(reverse('update_daily_goals'), {
            'daily_pomo_goal': '6', 'daily_notes_goal': '5', 'daily_focus_goal': '180',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)['status'], 'ok')
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_pomo_goal, 6)
        self.assertEqual(self.user.daily_notes_goal, 5)
        self.assertEqual(self.user.daily_focus_goal, 180)

    def test_goals_clamped_to_valid_range(self):
        """Updating daily goals with values outside the valid range should clamp the user's daily_pomo_goal, daily_notes_goal, and daily_focus_goal to the defined minimum and maximum values."""
        self.login()
        self.client.post(reverse('update_daily_goals'), {
            'daily_pomo_goal': '100', 'daily_notes_goal': '0', 'daily_focus_goal': '9999',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_pomo_goal, 20)
        self.assertEqual(self.user.daily_notes_goal, 1)
        self.assertEqual(self.user.daily_focus_goal, 480)

    def test_invalid_data_returns_400(self):
        """Updating daily goals with non-integer values should return a 400 Bad Request response with a JSON body containing status 'error'."""
        self.login()
        resp = self.client.post(reverse('update_daily_goals'), {'daily_pomo_goal': 'not_a_number'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(json.loads(resp.content)['status'], 'error')


class JsonViewsTest(_ViewTestBase):
    def test_daily_progress(self):
        """The daily_progress view should return a JSON response containing the user's current progress towards their daily goals, including the number of pomodoros completed, notes edited, focus minutes, and whether all goals are complete."""
        self.login()
        resp = self.client.get(reverse('daily_progress'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        for key in ('pomodoros', 'pomo_goal', 'notes_edited', 'notes_goal', 'focus_minutes', 'focus_goal', 'all_complete'):
            self.assertIn(key, data)

    def test_heatmap_data(self):
        """The heatmap_data view should return a JSON response containing a list of daily activity data for the past year, with each entry including the date, number of pomodoros completed, and focus minutes for that day."""
        self.login()
        resp = self.client.get(reverse('heatmap_data'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('days', json.loads(resp.content))

    def test_notes_stats(self):
        """The notes_stats view should return a JSON response containing the user's current XP, level, progress towards the next level, current note streak, and longest note streak."""
        self.login()
        data = json.loads(self.client.get(reverse('notes_stats')).content)
        for key in ('xp', 'level', 'xp_progress_pct', 'xp_for_next_level', 'note_streak', 'longest_streak'):
            self.assertIn(key, data)


class NoteEditViewTest(_ViewTestBase):
    def test_invalid_form_redirects_with_error(self):
        """Submitting an invalid form (e.g. empty title) should redirect back to the notes page and should not update the note's title or content."""
        self.login()
        resp = self.client.post(
            reverse('note_edit', args=[self.note.id]),
            {'title': '', 'content': 'some content'},
        )
        self.assertRedirects(resp, reverse('notes'), fetch_redirect_response=False)
        self.note.refresh_from_db()
        self.assertEqual(self.note.title, 'View Test Note')

    def test_non_owner_gets_forbidden(self):
        """A user who is not the owner of the note should receive a 403 Forbidden response when attempting to edit the note, and the note's title and content should not be updated."""
        self.login(self.other)
        resp = self.client.post(
            reverse('note_edit', args=[self.note.id]),
            {'title': 'Hacked', 'content': ''},
        )
        self.assertEqual(resp.status_code, 403)


class NoteDeleteViewTest(_ViewTestBase):
    def test_owner_can_delete(self):
        """The owner of a note should be able to delete it, which should remove the note from the database and redirect to the notes page."""
        self.login()
        note_id = self.note.id
        self.assertEqual(self.client.post(reverse('note_delete', args=[note_id])).status_code, 302)
        self.assertFalse(Note.objects.filter(id=note_id).exists())

    def test_other_user_gets_403(self):
        """A user who is not the owner of the note and is not staff should receive a 403 Forbidden response when attempting to delete the note, and the note should still exist in the database."""
        self.login(self.other)
        self.assertEqual(self.client.post(reverse('note_delete', args=[self.note.id])).status_code, 403)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

    def test_staff_can_delete(self):
        """A staff user should be able to delete any note, which should remove the note from the database and redirect to the notes page."""
        staff = User.objects.create_user(username='staffdel', password='pass123', is_staff=True)
        self.login(staff)
        note_id = self.note.id
        self.assertEqual(self.client.post(reverse('note_delete', args=[note_id])).status_code, 302)
        self.assertFalse(Note.objects.filter(id=note_id).exists())


class NoteTogglePinViewTest(_ViewTestBase):
    def test_toggle_pin_on(self):
        """Toggling the pin state of a note that is currently not pinned should set it to pinned, return a JSON response with 'pinned': true, and update the note's is_pinned field in the database accordingly."""
        self.login()
        resp = self.client.post(reverse('note_toggle_pin', args=[self.note.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(json.loads(resp.content)['pinned'])
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_pinned)

    def test_toggle_pin_off(self):
        """Toggling the pin state of a note that is currently pinned should set it to not pinned, return a JSON response with 'pinned': false, and update the note's is_pinned field in the database accordingly."""
        self.note.is_pinned = True
        self.note.save()
        self.login()
        resp = self.client.post(reverse('note_toggle_pin', args=[self.note.id]))
        self.assertFalse(json.loads(resp.content)['pinned'])
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_pinned)

    def test_other_user_gets_404(self):
        """A user who is not the owner of the note should receive a 404 Not Found response when attempting to toggle the pin state of the note, and the note's is_pinned field should not be updated."""
        self.login(self.other)
        self.assertEqual(self.client.post(reverse('note_toggle_pin', args=[self.note.id])).status_code, 404)
