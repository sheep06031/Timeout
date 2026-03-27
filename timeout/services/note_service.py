import datetime

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from timeout.models import Note, StudyLog


class NoteService:
    """Service for managing note query logic."""

    #Gamification helpers

    XP_NOTE_CREATE = 10
    XP_NOTE_EDIT = 5
    XP_POMODORO = 25
    XP_DAILY_GOALS_BONUS = 50

    @staticmethod
    def update_streak_and_xp(user, xp_base):
        """Update user's note streak and award XP. Call on note create/edit."""
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - datetime.timedelta(days=1)

        if user.last_note_date == today:
            user.xp += xp_base
            user.save(update_fields=['xp'])
            return

        if user.last_note_date == yesterday:
            user.note_streak += 1
        else:
            user.note_streak = 1

        if user.note_streak > user.longest_note_streak:
            user.longest_note_streak = user.note_streak

        streak_bonus = user.note_streak * 5
        user.xp += xp_base + streak_bonus
        user.last_note_date = today
        user.save(update_fields=['xp', 'note_streak', 'longest_note_streak', 'last_note_date'])

    @staticmethod
    def award_pomodoro_xp(user):
        """Award XP for completing a Pomodoro session."""
        user.xp += NoteService.XP_POMODORO
        user.save(update_fields=['xp'])


    @staticmethod
    def get_user_notes(user):
        """Get all notes for a user, pinned first then newest."""
        if not user.is_authenticated:
            return Note.objects.none()
        return Note.objects.filter(
            owner=user
        ).select_related('event').order_by(
            '-is_pinned', '-created_at'
        )


    @staticmethod
    def get_notes_by_category(user, category):
        """Get notes for a user filtered by category."""
        if not user.is_authenticated:
            return Note.objects.none()
        return Note.objects.filter(
            owner=user,
            category=category,
        ).select_related('event').order_by(
            '-is_pinned', '-created_at'
        )

    @staticmethod
    def get_notes_for_event(user, event_id):
        """Get notes linked to a specific event."""
        if not user.is_authenticated:
            return Note.objects.none()
        return Note.objects.filter(
            owner=user,
            event_id=event_id,
        ).select_related('event').order_by(
            '-is_pinned', '-created_at'
        )


    @staticmethod
    def search_notes(user, query):
        """Search notes by title or content."""
        if not user.is_authenticated:
            return Note.objects.none()
        return Note.objects.filter(
            owner=user,
        ).filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        ).select_related('event').order_by(
            '-is_pinned', '-created_at'
        )

    # StudyLog helpers

    @staticmethod
    def log_note_created(user):
        """Increment today's notes_created counter."""
        today = timezone.localtime(timezone.now()).date()
        log, _ = StudyLog.objects.get_or_create(user=user, date=today)
        log.notes_created += 1
        log.save(update_fields=['notes_created'])

    @staticmethod
    def log_note_edited(user):
        """Increment today's notes_edited counter."""
        today = timezone.localtime(timezone.now()).date()
        log, _ = StudyLog.objects.get_or_create(user=user, date=today)
        log.notes_edited += 1
        log.save(update_fields=['notes_edited'])

    @staticmethod
    def log_pomodoro(user, minutes):
        """Increment today's pomodoro counter and focus minutes."""
        today = timezone.localtime(timezone.now()).date()
        log, _ = StudyLog.objects.get_or_create(user=user, date=today)
        log.pomodoros += 1
        log.focus_minutes += minutes
        log.save(update_fields=['pomodoros', 'focus_minutes'])

    @staticmethod
    def get_heatmap_data(user, weeks=12):
        """Return last N weeks of daily activity for the heatmap."""
        today = timezone.localtime(timezone.now()).date()
        start = today - datetime.timedelta(days=weeks * 7 - 1)
        logs = StudyLog.objects.filter(
            user=user, date__gte=start, date__lte=today,
        ).order_by('date')
        log_map = {log.date: log for log in logs}

        data = []
        current = start
        while current <= today:
            log = log_map.get(current)
            data.append({
                'date': current.isoformat(),
                'level': log.activity_level if log else 0,
                'pomodoros': log.pomodoros if log else 0,
                'notes': log.notes_created if log else 0,
                'focus': log.focus_minutes if log else 0,
            })
            current += datetime.timedelta(days=1)
        return data

    @staticmethod
    def get_daily_progress(user):
        """Get today's progress vs daily goals."""
        today = timezone.localtime(timezone.now()).date()
        log, _ = StudyLog.objects.get_or_create(user=user, date=today)
        return {
            'pomodoros': log.pomodoros,
            'pomo_goal': user.daily_pomo_goal,
            'notes_edited': log.notes_edited,
            'notes_goal': user.daily_notes_goal,
            'focus_minutes': log.focus_minutes,
            'focus_goal': user.daily_focus_goal,
            'all_complete': (
                log.pomodoros >= user.daily_pomo_goal
                and log.notes_edited >= user.daily_notes_goal
                and log.focus_minutes >= user.daily_focus_goal
            ),
        }
