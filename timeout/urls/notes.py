"""
Note management related URL patterns for the timeout app.
"""

from django.urls import path
from timeout.views import notes
from timeout.views import notes_productivity as notes_prod

urlpatterns = [
    path('', notes.note_list, name='notes'),
    path('create/', notes.note_create, name='note_create'),
    path('<int:note_id>/edit/', notes.note_edit, name='note_edit'),
    path('<int:note_id>/autosave/', notes.note_autosave, name='note_autosave'),
    path('<int:note_id>/delete/', notes.note_delete, name='note_delete'),
    path('<int:note_id>/pin/', notes.note_toggle_pin, name='note_toggle_pin'),
    path('<int:note_id>/share/', notes.note_share, name='note_share'),
    path('pomodoro/complete/', notes_prod.pomodoro_complete, name='pomodoro_complete'),
    path('stats/', notes_prod.notes_stats, name='notes_stats'),
    path('heatmap/', notes_prod.heatmap_data, name='heatmap_data'),
    path('goals/update/', notes_prod.update_daily_goals, name='update_daily_goals'),
    path('goals/progress/', notes_prod.daily_progress, name='daily_progress'),
]
