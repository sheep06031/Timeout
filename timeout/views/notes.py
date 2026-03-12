import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from timeout.forms import NoteForm
from timeout.models import Note, Post
from timeout.services import NoteService


@login_required
def note_list(request):
    """List all notes with search and category filter."""
    category = request.GET.get('category', '')
    query = request.GET.get('q', '')
    filter_mode = request.GET.get('filter', '')

    if query:
        notes = NoteService.search_notes(request.user, query)
    elif category:
        notes = NoteService.get_notes_by_category(request.user, category)
    else:
        notes = NoteService.get_user_notes(request.user)

    # Due Soon filter: only notes with due dates, ordered by soonest
    if filter_mode == 'due_soon':
        from django.utils import timezone
        notes = notes.filter(
            due_date__isnull=False,
            due_date__gte=timezone.now(),
        ).order_by('due_date')

    user = request.user

    # Build note list for Pomodoro linking (id + title)
    user_notes_simple = list(
        Note.objects.filter(owner=user)
        .values_list('id', 'title')
        .order_by('-is_pinned', '-created_at')[:20]
    )

    context = {
        'notes': notes,
        'form': NoteForm(user=user),
        'categories': Note.Category.choices,
        'active_category': category,
        'search_query': query,
        'active_filter': filter_mode,
        # Gamification
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
        # Daily goals
        'daily_progress': NoteService.get_daily_progress(user),
        # Pomodoro note linking
        'user_notes_json': json.dumps(user_notes_simple),
    }
    return render(request, 'pages/notes.html', context)


@login_required
def note_create(request):
    """Create a new note."""
    if request.method == 'POST':
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            note = form.save(commit=False)
            note.owner = request.user
            note.save()
            NoteService.update_streak_and_xp(
                request.user, NoteService.XP_NOTE_CREATE,
            )
            NoteService.log_note_created(request.user)
            messages.success(request, 'Note created successfully!')
            return redirect('notes')
        else:
            messages.error(request, 'Error creating note.')
    return redirect('notes')


@login_required
def note_edit(request, note_id):
    """Edit an existing note."""
    note = get_object_or_404(Note, id=note_id)

    if not note.can_edit(request.user):
        return HttpResponseForbidden('You cannot edit this note.')

    if request.method == 'POST':
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            form.save()
            NoteService.update_streak_and_xp(
                request.user, NoteService.XP_NOTE_EDIT,
            )
            messages.success(request, 'Note updated successfully!')
            return redirect('notes')
        messages.error(request, 'Error updating note.')
        return redirect('notes')

    user = request.user
    form = NoteForm(instance=note, user=user)
    context = {
        'form': form,
        'note': note,
        # Gamification (for focus mode / stats bar on edit page)
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
    }
    return render(request, 'pages/note_edit.html', context)


@login_required
@require_POST
def note_delete(request, note_id):
    """Delete a note."""
    note = get_object_or_404(Note, id=note_id)

    if not note.can_delete(request.user):
        return HttpResponseForbidden('You cannot delete this note.')

    note.delete()
    messages.success(request, 'Note deleted successfully!')
    return redirect('notes')


@login_required
@require_POST
def note_toggle_pin(request, note_id):
    """Toggle pin status of a note."""
    note = get_object_or_404(Note, id=note_id, owner=request.user)
    note.is_pinned = not note.is_pinned
    note.save(update_fields=['is_pinned'])
    return JsonResponse({'pinned': note.is_pinned})


@login_required
@require_POST
def note_share(request, note_id):
    """Share a note as a social post."""
    note = get_object_or_404(Note, id=note_id, owner=request.user)
    content = f"[{note.get_category_display()}] {note.title}\n\n{note.content}"
    Post.objects.create(
        author=request.user,
        content=content[:5000],
        event=note.event,
        privacy=Post.Privacy.PUBLIC,
    )
    messages.success(request, 'Note shared as a post!')
    return redirect('social_feed')


@login_required
@require_POST
def pomodoro_complete(request):
    """Award XP when a Pomodoro work session is completed."""
    user = request.user
    cfg_work = user.pomo_work_minutes

    # Link to specific note if provided
    note_id = request.POST.get('note_id')
    if note_id:
        try:
            note = Note.objects.get(id=note_id, owner=user)
            note.time_spent_minutes += cfg_work
            note.save(update_fields=['time_spent_minutes'])
        except Note.DoesNotExist:
            pass

    NoteService.award_pomodoro_xp(user)
    NoteService.log_pomodoro(user, cfg_work)

    user.refresh_from_db()
    progress = NoteService.get_daily_progress(user)

    return JsonResponse({
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'daily_progress': progress,
    })


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

        return JsonResponse({'status': 'ok'})
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error'}, status=400)


@login_required
def daily_progress(request):
    """Return today's daily progress as JSON."""
    progress = NoteService.get_daily_progress(request.user)
    return JsonResponse(progress)
