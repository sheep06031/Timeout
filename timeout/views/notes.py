"""
Views for note management, including listing, creating, editing, deleting, and sharing notes.
"""

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


def _user_xp_context(user):
    """Return XP/streak fields shared across note page contexts."""
    return {
        'xp': user.xp,
        'level': user.level,
        'xp_progress_pct': user.xp_progress_pct,
        'xp_for_next_level': user.xp_for_next_level,
        'note_streak': user.note_streak,
        'longest_streak': user.longest_note_streak,
    }


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
        **_user_xp_context(user),
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


def _attach_event_to_note(note, event_id, user):
    """Attach an event to a note if event_id is valid."""
    if event_id:
        from timeout.models.event import Event
        try:
            note.event = Event.objects.get(pk=event_id, creator=user)
        except Event.DoesNotExist:
            pass


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
        note = Note(owner=request.user, title=title, content='', category=category)
        _attach_event_to_note(note, event_id, request.user)
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
        **_user_xp_context(user),
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

    return JsonResponse({'success': True, 'updated_at': note.updated_at.isoformat()})


@login_required
@require_POST
def note_delete(request, note_id):
    """Delete a note."""
    note = get_object_or_404(Note, id=note_id)

    if not note.can_delete(request.user):
        return HttpResponseForbidden('You cannot delete this note.')

    note.delete()
    if request.headers.get('X-CSRFToken'):
        return JsonResponse({'ok': True})
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


