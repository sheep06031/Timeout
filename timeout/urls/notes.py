"""
Note management related URL patterns for the timeout app.
Includes:
- note_list: View to display all notes for the current user.
- note_create: View to create a new note.
- note_edit: View to edit an existing note.
- note_autosave: Endpoint to autosave note content via AJAX.
- note_delete: Endpoint to delete a note.
- note_toggle_pin: Endpoint to pin/unpin a note.
- note_share: View to share a note with other users.
- pomodoro_complete: Endpoint to mark a pomodoro session as complete and optionally create a note about it.
- notes_stats: View to show statistics about the user's notes (e.g. number of notes, average length, etc.).
- heatmap_data: Endpoint to provide data for a heatmap visualization of note creation activity over time.
- update_daily_goals: Endpoint to update the user's daily note-taking goals.
- daily_progress: Endpoint to get the user's progress towards their daily note-taking goals.
"""

from django.urls import path
from timeout.views import notes

urlpatterns = [
    path('', notes.note_list, name='notes'),
    path('create/', notes.note_create, name='note_create'),
    path('<int:note_id>/edit/', notes.note_edit, name='note_edit'),
    path('<int:note_id>/autosave/', notes.note_autosave, name='note_autosave'),
    path('<int:note_id>/delete/', notes.note_delete, name='note_delete'),
    path('<int:note_id>/pin/', notes.note_toggle_pin, name='note_toggle_pin'),
    path('<int:note_id>/share/', notes.note_share, name='note_share'),
    path('pomodoro/complete/', notes.pomodoro_complete, name='pomodoro_complete'),
    path('stats/', notes.notes_stats, name='notes_stats'),
    path('heatmap/', notes.heatmap_data, name='heatmap_data'),
    path('goals/update/', notes.update_daily_goals, name='update_daily_goals'),
    path('goals/progress/', notes.daily_progress, name='daily_progress'),
]
