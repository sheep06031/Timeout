from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from timeout.models import Note
from timeout.services import NoteService


def _update_note_time(user, note_id, minutes):
    """Add pomodoro minutes to the linked note, if it exists."""
    if note_id:
        try:
            note = Note.objects.get(id=note_id, owner=user)
            note.time_spent_minutes += minutes
            note.save(update_fields=['time_spent_minutes'])
        except Note.DoesNotExist:
            pass


@login_required
@require_POST
def pomodoro_complete(request):
    """Award XP when a Pomodoro work session is completed."""
    user = request.user
    _update_note_time(user, request.POST.get('note_id'), user.pomo_work_minutes)
    NoteService.award_pomodoro_xp(user)
    NoteService.log_pomodoro(user, user.pomo_work_minutes)
    user.refresh_from_db()
    return JsonResponse({
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'daily_progress': NoteService.get_daily_progress(user)})


@login_required
def notes_stats(request):
    """Return gamification stats as JSON."""
    user = request.user
    return JsonResponse({
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
    })


@login_required
def heatmap_data(request):
    """Return study activity heatmap data as JSON."""
    data = NoteService.get_heatmap_data(request.user)
    return JsonResponse({'days': data})


@login_required
@require_POST
def update_daily_goals(request):
    """Update user's daily goal targets."""
    user = request.user
    try:
        pomo = int(request.POST.get('daily_pomo_goal', user.daily_pomo_goal))
        notes = int(request.POST.get('daily_notes_goal', user.daily_notes_goal))
        focus = int(request.POST.get('daily_focus_goal', user.daily_focus_goal))

        user.daily_pomo_goal = max(1, min(pomo, 20))
        user.daily_notes_goal = max(1, min(notes, 20))
        user.daily_focus_goal = max(10, min(focus, 480))
        user.save(update_fields=['daily_pomo_goal', 'daily_notes_goal', 'daily_focus_goal'])

        return JsonResponse({'success': True})
    except (ValueError, TypeError):
        return JsonResponse({'success': False}, status=400)


@login_required
def daily_progress(request):
    """Return today's daily progress as JSON."""
    progress = NoteService.get_daily_progress(request.user)
    return JsonResponse(progress)
