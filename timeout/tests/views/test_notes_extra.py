import datetime
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from timeout.models import Note, Post, StudyLog
from timeout.services import NoteService

User = get_user_model()


# Note model property tests
class NoteUrgencyTest(TestCase):
    """Tests for Note.urgency property across all levels."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='urgency_user', password='pass123'
        )
        self.note = Note.objects.create(
            owner=self.user,
            title='Urgency Test',
            content='',
            category=Note.Category.OTHER,
        )

    def test_urgency_no_due_date_returns_none(self):
        self.assertIsNone(self.note.due_date)
        self.assertIsNone(self.note.urgency)

    def test_urgency_overdue(self):
        self.note.due_date = timezone.now() - datetime.timedelta(hours=1)
        self.note.save()
        self.assertEqual(self.note.urgency, 'overdue')

    def test_urgency_urgent_within_24h(self):
        self.note.due_date = timezone.now() + datetime.timedelta(hours=12)
        self.note.save()
        self.assertEqual(self.note.urgency, 'urgent')

    def test_urgency_soon_within_72h(self):
        self.note.due_date = timezone.now() + datetime.timedelta(hours=48)
        self.note.save()
        self.assertEqual(self.note.urgency, 'soon')

    def test_urgency_upcoming_beyond_72h(self):
        self.note.due_date = timezone.now() + datetime.timedelta(days=7)
        self.note.save()
        self.assertEqual(self.note.urgency, 'upcoming')


class NoteTimeSpentDisplayTest(TestCase):
    """Tests for Note.time_spent_display property."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='display_user', password='pass123'
        )
        self.note = Note.objects.create(
            owner=self.user,
            title='Display Test',
            content='',
            category=Note.Category.OTHER,
        )

    def test_zero_minutes_returns_empty_string(self):
        self.note.time_spent_minutes = 0
        self.assertEqual(self.note.time_spent_display, '')

    def test_minutes_only(self):
        self.note.time_spent_minutes = 45
        self.assertEqual(self.note.time_spent_display, '45m')

    def test_hours_only(self):
        self.note.time_spent_minutes = 120
        self.assertEqual(self.note.time_spent_display, '2h')

    def test_hours_and_minutes(self):
        self.note.time_spent_minutes = 90
        self.assertEqual(self.note.time_spent_display, '1h 30m')


class NoteCanEditTest(TestCase):
    """Tests for Note.can_edit method."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_edit', password='pass123'
        )
        self.other = User.objects.create_user(
            username='other_edit', password='pass123'
        )
        self.note = Note.objects.create(
            owner=self.owner,
            title='Edit Permission',
            content='',
            category=Note.Category.OTHER,
        )

    def test_unauthenticated_returns_false(self):
        self.assertFalse(self.note.can_edit(AnonymousUser()))

    def test_owner_returns_true(self):
        self.assertTrue(self.note.can_edit(self.owner))

    def test_other_user_returns_false(self):
        self.assertFalse(self.note.can_edit(self.other))


class NoteCanDeleteTest(TestCase):
    """Tests for Note.can_delete method."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_del', password='pass123'
        )
        self.other = User.objects.create_user(
            username='other_del', password='pass123'
        )
        self.staff = User.objects.create_user(
            username='staff_del', password='pass123', is_staff=True
        )
        self.note = Note.objects.create(
            owner=self.owner,
            title='Delete Permission',
            content='',
            category=Note.Category.OTHER,
        )

    def test_unauthenticated_returns_false(self):
        self.assertFalse(self.note.can_delete(AnonymousUser()))

    def test_owner_returns_true(self):
        self.assertTrue(self.note.can_delete(self.owner))

    def test_staff_returns_true(self):
        self.assertTrue(self.note.can_delete(self.staff))

    def test_other_user_returns_false(self):
        self.assertFalse(self.note.can_delete(self.other))


# StudyLog model tests
class StudyLogModelTest(TestCase):
    """Tests for StudyLog __str__ and activity_level property."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='loguser', password='pass123'
        )
        self.today = timezone.localtime(timezone.now()).date()

    def test_str_representation(self):
        log = StudyLog.objects.create(user=self.user, date=self.today)
        expected = f'{self.user.username} \u2014 {self.today}'
        self.assertEqual(str(log), expected)

    def test_activity_level_0_score_zero(self):
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=0, notes_created=0, notes_edited=0, focus_minutes=0,
        )
        self.assertEqual(log.activity_level, 0)

    def test_activity_level_1_score_low(self):
        # score = 0*2 + 1 + 0 + 0//30 = 1  -> level 1
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=0, notes_created=1, notes_edited=0, focus_minutes=0,
        )
        self.assertEqual(log.activity_level, 1)

    def test_activity_level_2_score_medium(self):
        # score = 1*2 + 1 + 0 + 0//30 = 3  -> level 2
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=1, notes_created=1, notes_edited=0, focus_minutes=0,
        )
        self.assertEqual(log.activity_level, 2)

    def test_activity_level_3_score_high(self):
        # score = 2*2 + 1 + 1 + 30//30 = 7  -> level 3
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=2, notes_created=1, notes_edited=1, focus_minutes=30,
        )
        self.assertEqual(log.activity_level, 3)

    def test_activity_level_4_score_very_high(self):
        # score = 5*2 + 2 + 1 + 60//30 = 15  -> level 4
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=5, notes_created=2, notes_edited=1, focus_minutes=60,
        )
        self.assertEqual(log.activity_level, 4)

# NoteService tests (log_pomodoro, get_heatmap_data, get_daily_progress, award_pomodoro_xp, update_streak_and_xp)
class NoteServicePomodoroTest(TestCase):
    """Tests for NoteService Pomodoro / gamification helpers."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_pomo', password='pass123'
        )
        self.today = timezone.localtime(timezone.now()).date()

    def test_log_pomodoro_creates_study_log(self):
        NoteService.log_pomodoro(self.user, 25)
        log = StudyLog.objects.get(user=self.user, date=self.today)
        self.assertEqual(log.pomodoros, 1)
        self.assertEqual(log.focus_minutes, 25)

    def test_log_pomodoro_increments_existing_log(self):
        NoteService.log_pomodoro(self.user, 25)
        NoteService.log_pomodoro(self.user, 25)
        log = StudyLog.objects.get(user=self.user, date=self.today)
        self.assertEqual(log.pomodoros, 2)
        self.assertEqual(log.focus_minutes, 50)

    def test_award_pomodoro_xp(self):
        initial_xp = self.user.xp
        NoteService.award_pomodoro_xp(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, initial_xp + NoteService.XP_POMODORO)

    def test_get_daily_progress_structure(self):
        progress = NoteService.get_daily_progress(self.user)
        self.assertIn('pomodoros', progress)
        self.assertIn('pomo_goal', progress)
        self.assertIn('notes_edited', progress)
        self.assertIn('notes_goal', progress)
        self.assertIn('focus_minutes', progress)
        self.assertIn('focus_goal', progress)
        self.assertIn('all_complete', progress)

    def test_get_daily_progress_all_complete_false_initially(self):
        progress = NoteService.get_daily_progress(self.user)
        self.assertFalse(progress['all_complete'])

    def test_get_heatmap_data_returns_list(self):
        data = NoteService.get_heatmap_data(self.user)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        # Each entry should have expected keys
        entry = data[0]
        self.assertIn('date', entry)
        self.assertIn('level', entry)
        self.assertIn('pomodoros', entry)
        self.assertIn('notes', entry)
        self.assertIn('focus', entry)

    def test_get_heatmap_data_includes_logged_day(self):
        NoteService.log_pomodoro(self.user, 25)
        data = NoteService.get_heatmap_data(self.user)
        today_str = self.today.isoformat()
        today_entry = next((d for d in data if d['date'] == today_str), None)
        self.assertIsNotNone(today_entry)
        self.assertEqual(today_entry['pomodoros'], 1)
        self.assertEqual(today_entry['focus'], 25)


class NoteServiceStreakTest(TestCase):
    """Tests for NoteService.update_streak_and_xp."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svc_streak', password='pass123'
        )

    def test_first_activity_starts_streak_at_1(self):
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_CREATE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 1)
        self.assertEqual(self.user.longest_note_streak, 1)

    def test_same_day_activity_does_not_increase_streak(self):
        today = timezone.localtime(timezone.now()).date()
        self.user.last_note_date = today
        self.user.note_streak = 3
        self.user.longest_note_streak = 5
        self.user.save()
        xp_before = self.user.xp
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_EDIT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 3)  # unchanged
        self.assertEqual(self.user.xp, xp_before + NoteService.XP_NOTE_EDIT)

    def test_consecutive_day_increases_streak(self):
        yesterday = timezone.localtime(timezone.now()).date() - datetime.timedelta(days=1)
        self.user.last_note_date = yesterday
        self.user.note_streak = 2
        self.user.longest_note_streak = 2
        self.user.save()
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_CREATE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 3)
        self.assertEqual(self.user.longest_note_streak, 3)

    def test_gap_resets_streak_to_1(self):
        old_date = timezone.localtime(timezone.now()).date() - datetime.timedelta(days=5)
        self.user.last_note_date = old_date
        self.user.note_streak = 10
        self.user.longest_note_streak = 10
        self.user.save()
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_CREATE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 1)
        # longest should remain unchanged since 1 < 10
        self.assertEqual(self.user.longest_note_streak, 10)

# View tests
class _ViewTestBase(TestCase):
    """Shared setUp for view tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser', password='pass123'
        )
        self.other = User.objects.create_user(
            username='viewother', password='pass123'
        )
        self.note = Note.objects.create(
            owner=self.user,
            title='View Test Note',
            content='<p>Hello world</p>',
            category=Note.Category.LECTURE,
        )

    def login(self, user=None):
        user = user or self.user
        ok = self.client.login(username=user.username, password='pass123')
        self.assertTrue(ok)


class PomodoroCompleteViewTest(_ViewTestBase):
    """Tests for pomodoro_complete view."""

    def test_pomodoro_complete_without_note_id(self):
        self.login()
        resp = self.client.post(reverse('pomodoro_complete'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('xp', data)
        self.assertIn('level', data)
        self.assertIn('daily_progress', data)

    def test_pomodoro_complete_with_note_id(self):
        self.login()
        initial_minutes = self.note.time_spent_minutes
        resp = self.client.post(
            reverse('pomodoro_complete'),
            {'note_id': self.note.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.note.refresh_from_db()
        expected = initial_minutes + self.user.pomo_work_minutes
        self.assertEqual(self.note.time_spent_minutes, expected)

    def test_pomodoro_complete_with_nonexistent_note_id(self):
        self.login()
        resp = self.client.post(
            reverse('pomodoro_complete'),
            {'note_id': 99999},
        )
        # Should succeed gracefully (the except Note.DoesNotExist passes)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('xp', data)

    def test_pomodoro_complete_awards_xp(self):
        self.login()
        xp_before = self.user.xp
        self.client.post(reverse('pomodoro_complete'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, xp_before + NoteService.XP_POMODORO)

    def test_pomodoro_complete_creates_study_log(self):
        self.login()
        self.client.post(reverse('pomodoro_complete'))
        today = timezone.localtime(timezone.now()).date()
        log = StudyLog.objects.get(user=self.user, date=today)
        self.assertEqual(log.pomodoros, 1)
        self.assertEqual(log.focus_minutes, self.user.pomo_work_minutes)


class NoteShareViewTest(_ViewTestBase):
    """Tests for note_share view."""

    def test_share_creates_post(self):
        self.login()
        resp = self.client.post(reverse('note_share', args=[self.note.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Post.objects.filter(author=self.user).exists())

    def test_shared_post_contains_note_content(self):
        self.login()
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertIn('View Test Note', post.content)
        self.assertIn('[Lecture]', post.content)
        # HTML should be stripped
        self.assertIn('Hello world', post.content)
        self.assertNotIn('<p>', post.content)

    def test_shared_post_is_public(self):
        self.login()
        self.client.post(reverse('note_share', args=[self.note.id]))
        post = Post.objects.get(author=self.user)
        self.assertEqual(post.privacy, Post.Privacy.PUBLIC)


class UpdateDailyGoalsViewTest(_ViewTestBase):
    """Tests for update_daily_goals view."""

    def test_valid_data_updates_goals(self):
        self.login()
        resp = self.client.post(reverse('update_daily_goals'), {
            'daily_pomo_goal': '6',
            'daily_notes_goal': '5',
            'daily_focus_goal': '180',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'ok')
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_pomo_goal, 6)
        self.assertEqual(self.user.daily_notes_goal, 5)
        self.assertEqual(self.user.daily_focus_goal, 180)

    def test_goals_clamped_to_valid_range(self):
        self.login()
        self.client.post(reverse('update_daily_goals'), {
            'daily_pomo_goal': '100',   # max 20
            'daily_notes_goal': '0',    # min 1
            'daily_focus_goal': '9999', # max 480
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.daily_pomo_goal, 20)
        self.assertEqual(self.user.daily_notes_goal, 1)
        self.assertEqual(self.user.daily_focus_goal, 480)

    def test_invalid_data_returns_400(self):
        self.login()
        resp = self.client.post(reverse('update_daily_goals'), {
            'daily_pomo_goal': 'not_a_number',
        })
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'error')


class DailyProgressViewTest(_ViewTestBase):
    """Tests for daily_progress view."""

    def test_returns_json(self):
        self.login()
        resp = self.client.get(reverse('daily_progress'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        data = json.loads(resp.content)
        self.assertIn('pomodoros', data)
        self.assertIn('pomo_goal', data)
        self.assertIn('notes_edited', data)
        self.assertIn('notes_goal', data)
        self.assertIn('focus_minutes', data)
        self.assertIn('focus_goal', data)
        self.assertIn('all_complete', data)

    def test_requires_login(self):
        resp = self.client.get(reverse('daily_progress'))
        self.assertEqual(resp.status_code, 302)


class HeatmapDataViewTest(_ViewTestBase):
    """Tests for heatmap_data view."""

    def test_returns_json_with_days_key(self):
        self.login()
        resp = self.client.get(reverse('heatmap_data'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        data = json.loads(resp.content)
        self.assertIn('days', data)
        self.assertIsInstance(data['days'], list)

    def test_requires_login(self):
        resp = self.client.get(reverse('heatmap_data'))
        self.assertEqual(resp.status_code, 302)


class NotesStatsViewTest(_ViewTestBase):
    """Tests for notes_stats view."""

    def test_returns_json_with_gamification_keys(self):
        self.login()
        resp = self.client.get(reverse('notes_stats'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('xp', data)
        self.assertIn('level', data)
        self.assertIn('xp_progress_pct', data)
        self.assertIn('xp_for_next_level', data)
        self.assertIn('note_streak', data)
        self.assertIn('longest_streak', data)

    def test_requires_login(self):
        resp = self.client.get(reverse('notes_stats'))
        self.assertEqual(resp.status_code, 302)


class NoteDeleteViewTest(_ViewTestBase):
    """Tests for note_delete view -- owner vs forbidden."""

    def test_owner_can_delete(self):
        self.login()
        note_id = self.note.id
        resp = self.client.post(reverse('note_delete', args=[note_id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Note.objects.filter(id=note_id).exists())

    def test_other_user_gets_403(self):
        self.login(self.other)
        resp = self.client.post(reverse('note_delete', args=[self.note.id]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Note.objects.filter(id=self.note.id).exists())

    def test_staff_can_delete(self):
        staff = User.objects.create_user(
            username='staffdel', password='pass123', is_staff=True,
        )
        self.login(staff)
        note_id = self.note.id
        resp = self.client.post(reverse('note_delete', args=[note_id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Note.objects.filter(id=note_id).exists())


class NoteTogglePinViewTest(_ViewTestBase):
    """Tests for note_toggle_pin view."""

    def test_toggle_pin_on(self):
        self.login()
        self.assertFalse(self.note.is_pinned)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['pinned'])
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_pinned)

    def test_toggle_pin_off(self):
        self.note.is_pinned = True
        self.note.save()
        self.login()
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertFalse(data['pinned'])
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_pinned)

    def test_other_user_gets_404(self):
        self.login(self.other)
        resp = self.client.post(
            reverse('note_toggle_pin', args=[self.note.id])
        )
        self.assertEqual(resp.status_code, 404)
