from django.urls import path

from timeout.views import notes

urlpatterns = [
    path('', notes.note_list, name='notes'),
    path('create/', notes.note_create, name='note_create'),
    path('<int:note_id>/edit/', notes.note_edit, name='note_edit'),
    path('<int:note_id>/delete/', notes.note_delete, name='note_delete'),
    path('<int:note_id>/pin/', notes.note_toggle_pin, name='note_toggle_pin'),
    path('<int:note_id>/share/', notes.note_share, name='note_share'),
    path('pomodoro/complete/', notes.pomodoro_complete, name='pomodoro_complete'),
    path('stats/', notes.notes_stats, name='notes_stats'),
]
