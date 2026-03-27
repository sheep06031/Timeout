import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from django.utils.html import strip_tags

from timeout.forms import NoteForm
from timeout.models import Note, Post
from timeout.services import NoteService


SORT_OPTIONS = {
    'newest': ('-created_at', 'Newest First'),
    'oldest': ('created_at', 'Oldest First'),
    'alpha_asc': ('title', 'A - Z'),
    'alpha_desc': ('-title', 'Z - A'),
    'recently_edited': ('-updated_at', 'Recently Edited'),
    'category': ('category', 'Category'),
}
DEFAULT_SORT = 'recently_edited'


def _get_filtered_notes(user, query, category, sort):
    """Filter and sort notes based on search query, category, and sort option."""
    if query:
        notes = NoteService.search_notes(user, query)
    elif category:
        notes = NoteService.get_notes_by_category(user, category)
    else:
        notes = NoteService.get_user_notes(user)
    if sort in SORT_OPTIONS:
        order_field = SORT_OPTIONS[sort][0]
        notes = notes.order_by('-is_pinned', order_field)
    return notes


def _build_note_list_context(user, notes, category, query, sort):
    """Assemble context dict for the note list page."""
    user_notes_simple = list(
        Note.objects.filter(owner=user)
        .values_list('id', 'title')
        .order_by('-is_pinned', '-created_at')[:20]
    )
    return {
        'notes': notes,
        'form': NoteForm(user=user),
        'categories': Note.Category.choices,
        'active_category': category,
        'search_query': query,
        'active_sort': sort,
        'sort_options': [(k, v[1]) for k, v in SORT_OPTIONS.items()],
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
        'daily_progress': NoteService.get_daily_progress(user),
        'user_notes_json': json.dumps(user_notes_simple),
    }


@login_required
def note_list(request):
    """List all notes with search, category filter, and sorting."""
    category = request.GET.get('category', '')
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', DEFAULT_SORT)
    notes = _get_filtered_notes(request.user, query, category, sort)
    context = _build_note_list_context(request.user, notes, category, query, sort)
    return render(request, 'pages/notes.html', context)


@login_required
def note_create(request):
    """Create a new note with title/category/event, then redirect to editor."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'other')
        event_id = request.POST.get('event', '')
        if not title:
            messages.error(request, 'Please provide a title for your note.')
            return redirect('notes')
        note = Note(
            owner=request.user,
            title=title,
            content='',
            category=category)
        if event_id:
            from timeout.models.event import Event
            try:
                note.event = Event.objects.get(pk=event_id, creator=request.user)
            except Event.DoesNotExist:
                pass

        note.save()
        NoteService.update_streak_and_xp(request.user, NoteService.XP_NOTE_CREATE)
        NoteService.log_note_created(request.user)
        return redirect('note_edit', note_id=note.id)
    return redirect('notes')


def _handle_note_edit_post(request, note):
    """Process note edit form submission."""
    form = NoteForm(request.POST, instance=note, user=request.user)
    if form.is_valid():
        form.save()
        NoteService.update_streak_and_xp(request.user, NoteService.XP_NOTE_EDIT)
        NoteService.log_note_edited(request.user)
        messages.success(request, 'Note saved successfully!')
        return redirect('notes')
    messages.error(request, 'Error updating note.')
    return redirect('notes')


@login_required
def note_edit(request, note_id):
    """Edit an existing note — full-page rich text editor."""
    note = get_object_or_404(Note, id=note_id)
    if not note.can_edit(request.user):
        return HttpResponseForbidden('You cannot edit this note.')
    if request.method == 'POST':
        return _handle_note_edit_post(request, note)
    user = request.user
    form = NoteForm(instance=note, user=user)
    context = {
        'form': form,
        'note': note,
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
def note_autosave(request, note_id):
    """Autosave note content via AJAX."""
    note = get_object_or_404(Note, id=note_id, owner=request.user)

    content = request.POST.get('content', '')
    title = request.POST.get('title', '').strip()

    update_fields = ['content', 'title', 'updated_at']

    if title:
        note.title = title
    note.content = content

    page_mode = request.POST.get('page_mode', '').strip()
    if page_mode in ('pageless', 'paged'):
        note.page_mode = page_mode
        update_fields.append('page_mode')

    note.save(update_fields=update_fields)

    if request.POST.get('count_edit') == '1':
        NoteService.log_note_edited(request.user)

    return JsonResponse({'status': 'ok', 'updated_at': note.updated_at.isoformat()})


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
    plain_content = strip_tags(note.content)
    content = f"[{note.get_category_display()}] {note.title}\n\n{plain_content}"
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
        'daily_progress': progress})

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
