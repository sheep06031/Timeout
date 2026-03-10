import datetime

from django.db.models import Q
from django.utils import timezone

from timeout.models import Note


class NoteService:
    """Service for managing note query logic."""

    # --- Gamification helpers ---

    XP_NOTE_CREATE = 10
    XP_NOTE_EDIT = 5
    XP_POMODORO = 25

    @staticmethod
    def update_streak_and_xp(user, xp_base):
        """Update user's note streak and award XP. Call on note create/edit."""
        today = timezone.localtime(timezone.now()).date()
        yesterday = today - datetime.timedelta(days=1)

        if user.last_note_date == today:
            # Already counted today — just award XP without streak change
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
        user.save(update_fields=[
            'xp', 'note_streak', 'longest_note_streak', 'last_note_date',
        ])

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
