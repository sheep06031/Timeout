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

    if query:
        notes = NoteService.search_notes(request.user, query)
    elif category:
        notes = NoteService.get_notes_by_category(request.user, category)
    else:
        notes = NoteService.get_user_notes(request.user)

    user = request.user
    context = {
        'notes': notes,
        'form': NoteForm(user=user),
        'categories': Note.Category.choices,
        'active_category': category,
        'search_query': query,
        # Gamification
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
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
    NoteService.award_pomodoro_xp(request.user)
    user = request.user
    user.refresh_from_db()
    return JsonResponse({
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
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
