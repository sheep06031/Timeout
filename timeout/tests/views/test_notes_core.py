"""
Tests for the core functionality of the Note model and NoteService in the timeout app, which includes properties and methods related to note urgency, time spent display, permissions, study logs, pomodoro logging, XP awarding, daily progress calculation, heatmap data generation, and streak tracking.
"""
import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone
from timeout.models import Note, StudyLog
from timeout.services import NoteService

User = get_user_model()

class NoteUrgencyTest(TestCase):
    """"Tests for the urgency property of the Note model, which determines how urgent a note is based on its due date."""
    def setUp(self):
        """Create a user and a note for testing."""
        self.user = User.objects.create_user(username='urgency_user', password='pass123')
        self.note = Note.objects.create(
            owner=self.user, title='Urgency Test', content='', category=Note.Category.OTHER,
        )

    def test_no_due_date_returns_none(self):
        """If a note has no due date, its urgency should be None."""
        self.assertIsNone(self.note.urgency)

    def test_overdue(self):
        """ If a note's due date is in the past, its urgency should be 'overdue'."""
        self.note.due_date = timezone.now() - datetime.timedelta(hours=1)
        self.note.save()
        self.assertEqual(self.note.urgency, 'overdue')

    def test_urgency_levels(self):
        """ A note's urgency should be 'urgent' if due within 24 hours, 'soon' if due within 3 days, and 'upcoming' if due within a week."""
        for delta, expected in [
            (datetime.timedelta(hours=12), 'urgent'),
            (datetime.timedelta(hours=48), 'soon'),
            (datetime.timedelta(days=7), 'upcoming'),
        ]:
            self.note.due_date = timezone.now() + delta
            self.note.save()
            self.assertEqual(self.note.urgency, expected)


class NoteTimeSpentDisplayTest(TestCase):
    """Tests for the time_spent_display property of the Note model, which formats the time spent on a note in a human-readable way."""
    def setUp(self):
        """Create a user and a note for testing."""
        self.user = User.objects.create_user(username='display_user', password='pass123')
        self.note = Note.objects.create(
            owner=self.user, title='Display Test', content='', category=Note.Category.OTHER,
        )

    def test_zero_returns_empty(self):
        """ If time_spent_minutes is 0, time_spent_display should return an empty string."""
        self.note.time_spent_minutes = 0
        self.assertEqual(self.note.time_spent_display, '')

    def test_minutes_only(self):
        """ If time_spent_minutes is less than 60, time_spent_display should return the minutes followed by 'm'."""
        self.note.time_spent_minutes = 45
        self.assertEqual(self.note.time_spent_display, '45m')

    def test_hours_only(self):
        """ If time_spent_minutes is a multiple of 60, time_spent_display should return the hours followed by 'h'."""
        self.note.time_spent_minutes = 120
        self.assertEqual(self.note.time_spent_display, '2h')

    def test_hours_and_minutes(self):
        """ If time_spent_minutes is greater than 60 and not a multiple of 60, time_spent_display should return the hours followed by 'h' and the remaining minutes followed by 'm'."""
        self.note.time_spent_minutes = 90
        self.assertEqual(self.note.time_spent_display, '1h 30m')


class NotePermissionsTest(TestCase):
    """Tests for the can_edit and can_delete methods of the Note model, which determine whether a user has permission to edit or delete a note."""
    def setUp(self):
        """Create a user, a staff user, and a note for testing."""
        self.owner = User.objects.create_user(username='owner_perm', password='pass123')
        self.other = User.objects.create_user(username='other_perm', password='pass123')
        self.staff = User.objects.create_user(username='staff_perm', password='pass123', is_staff=True)
        self.note = Note.objects.create(
            owner=self.owner, title='Perm Test', content='', category=Note.Category.OTHER,
        )

    def test_can_edit(self):
        """Only the owner should be able to edit a note; staff and other users should not have edit permissions."""
        self.assertFalse(self.note.can_edit(AnonymousUser()))
        self.assertTrue(self.note.can_edit(self.owner))
        self.assertFalse(self.note.can_edit(self.other))

    def test_can_delete(self):
        """The owner and staff should be able to delete a note, but other users should not have delete permissions."""
        self.assertFalse(self.note.can_delete(AnonymousUser()))
        self.assertTrue(self.note.can_delete(self.owner))
        self.assertTrue(self.note.can_delete(self.staff))
        self.assertFalse(self.note.can_delete(self.other))


class StudyLogModelTest(TestCase):
    """Tests for the StudyLog model, which tracks a user's study activity for each day and calculates an activity level based on that activity."""
    def setUp(self):
        """Create a user for testing."""
        self.user = User.objects.create_user(username='loguser', password='pass123')
        self.today = timezone.localtime(timezone.now()).date()

    def test_str_representation(self):
        """The string representation of a StudyLog should include the username and date."""
        log = StudyLog.objects.create(user=self.user, date=self.today)
        self.assertEqual(str(log), f'{self.user.username} \u2014 {self.today}')

    def test_activity_level_0(self):
        """A StudyLog with no activity (0 pomodoros, 0 notes created/edited, 0 focus minutes) should have an activity level of 0."""
        log = StudyLog.objects.create(
            user=self.user, date=self.today,
            pomodoros=0, notes_created=0, notes_edited=0, focus_minutes=0,
        )
        self.assertEqual(log.activity_level, 0)

    def test_activity_levels_1_to_4(self):
        """A StudyLog's activity level should increase based on the amount of activity, with specific thresholds for pomodoros, notes created/edited, and focus minutes."""
        cases = [
            (dict(pomodoros=0, notes_created=1, notes_edited=0, focus_minutes=0), 1),
            (dict(pomodoros=1, notes_created=1, notes_edited=0, focus_minutes=0), 2),
            (dict(pomodoros=2, notes_created=1, notes_edited=1, focus_minutes=30), 3),
            (dict(pomodoros=5, notes_created=2, notes_edited=1, focus_minutes=60), 4),
        ]
        for i, (fields, expected) in enumerate(cases):
            log = StudyLog.objects.create(
                user=self.user, date=self.today - datetime.timedelta(days=i + 1), **fields,
            )
            self.assertEqual(log.activity_level, expected)


class NoteServicePomodoroTest(TestCase):
    """Tests for the NoteService methods related to logging pomodoros, awarding XP, and calculating daily progress and heatmap data."""
    def setUp(self):
        """Create a user for testing."""
        self.user = User.objects.create_user(username='svc_pomo', password='pass123')
        self.today = timezone.localtime(timezone.now()).date()

    def test_log_pomodoro_creates_study_log(self):
        """If no StudyLog exists for the user and date, log_pomodoro should create one with the correct pomodoro and focus minute counts."""
        NoteService.log_pomodoro(self.user, 25)
        log = StudyLog.objects.get(user=self.user, date=self.today)
        self.assertEqual(log.pomodoros, 1)
        self.assertEqual(log.focus_minutes, 25)

    def test_log_pomodoro_increments_existing_log(self):
        """If a StudyLog already exists for the user and date, log_pomodoro should increment the pomodoro and focus minute counts appropriately."""
        NoteService.log_pomodoro(self.user, 25)
        NoteService.log_pomodoro(self.user, 25)
        log = StudyLog.objects.get(user=self.user, date=self.today)
        self.assertEqual(log.pomodoros, 2)
        self.assertEqual(log.focus_minutes, 50)

    def test_award_pomodoro_xp(self):
        """award_pomodoro_xp should increase the user's XP by the correct amount defined in NoteService.XP_POMODORO."""
        initial_xp = self.user.xp
        NoteService.award_pomodoro_xp(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, initial_xp + NoteService.XP_POMODORO)

    def test_get_daily_progress_structure(self):
        """get_daily_progress should return a dictionary containing keys for pomodoros, pomo_goal, notes_edited, notes_goal, focus_minutes, focus_goal, and all_complete."""
        progress = NoteService.get_daily_progress(self.user)
        for key in ('pomodoros', 'pomo_goal', 'notes_edited', 'notes_goal', 'focus_minutes', 'focus_goal', 'all_complete'):
            self.assertIn(key, progress)
        self.assertFalse(progress['all_complete'])

    def test_get_heatmap_data(self):
        """get_heatmap_data should return a list of dictionaries with date, pomodoros, and focus keys, and should include an entry for today with the correct counts after logging a pomodoro."""
        NoteService.log_pomodoro(self.user, 25)
        data = NoteService.get_heatmap_data(self.user)
        self.assertIsInstance(data, list)
        today_str = self.today.isoformat()
        today_entry = next((d for d in data if d['date'] == today_str), None)
        self.assertIsNotNone(today_entry)
        self.assertEqual(today_entry['pomodoros'], 1)
        self.assertEqual(today_entry['focus'], 25)


class NoteServiceStreakTest(TestCase):
    """Tests for the NoteService method update_streak_and_xp, which updates a user's note streak and awards XP based on note-related activity."""
    def setUp(self):
        """Create a user for testing."""
        self.user = User.objects.create_user(username='svc_streak', password='pass123')

    def test_first_activity_starts_streak_at_1(self):
        """When a user performs a note-related activity for the first time (with no prior streak), their note streak should start at 1, and longest_note_streak should also be updated to 1."""
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_CREATE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 1)
        self.assertEqual(self.user.longest_note_streak, 1)

    def test_same_day_does_not_increase_streak(self):
        """If a user performs multiple note-related activities on the same day, their note streak should not increase more than once for that day, but they should still earn XP for each activity."""
        today = timezone.localtime(timezone.now()).date()
        self.user.last_note_date = today
        self.user.note_streak = 3
        self.user.longest_note_streak = 5
        self.user.save()
        xp_before = self.user.xp
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_EDIT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 3)
        self.assertEqual(self.user.xp, xp_before + NoteService.XP_NOTE_EDIT)

    def test_consecutive_day_increases_streak(self):
        """If a user performs a note-related activity on the day immediately following their last_note_date, their note streak should increase by 1, and longest_note_streak should be updated if the new streak is the longest."""
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
        """If a user performs a note-related activity after a gap of more than one day since their last_note_date, their note streak should reset to 1, but longest_note_streak should not change unless the previous streak was the longest."""
        old_date = timezone.localtime(timezone.now()).date() - datetime.timedelta(days=5)
        self.user.last_note_date = old_date
        self.user.note_streak = 10
        self.user.longest_note_streak = 10
        self.user.save()
        NoteService.update_streak_and_xp(self.user, NoteService.XP_NOTE_CREATE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.note_streak, 1)
        self.assertEqual(self.user.longest_note_streak, 10)


