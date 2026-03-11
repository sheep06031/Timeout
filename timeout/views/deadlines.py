from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from timeout.services.deadline_service import DeadlineService
from timeout.services.notification_service import NotificationService

# Display labels and ordering for each event type section
_TYPE_META = [
    ('deadline',      'Deadlines'),
    ('study_session', 'Study Sessions'),
    ('exam',          'Exams'),
    ('class',         'Classes'),
    ('meeting',       'Meetings'),
    ('other',         'Other'),
]


@login_required
def deadline_list_view(request):
    """Renders the list view showing all active events grouped by type."""
    events_by_type = DeadlineService.get_all_active_events(request.user)

    # Build ordered sections (skip empty types)
    sections = [
        {'type_key': key, 'label': label, 'items': events_by_type[key]}
        for key, label in _TYPE_META
        if key in events_by_type
    ]

    all_items = [item for items in events_by_type.values() for item in items]

    NotificationService.create_deadline_notifications(request.user)

    context = {
        'deadlines': deadlines,
        'total_count': len(deadlines),
        'overdue_count': sum(1 for d in deadlines if d['urgency_status'] == 'overdue'), # Get how much assignments are overdue
        # Get how much assignments are urgent
        'urgent_count': sum(1 for d in deadlines if d['urgency_status'] == 'urgent'),

        'unread_notifications': request.user.notifications.filter(is_read=False),
        'sections': sections,
        'total_count': len(all_items),
        'overdue_count': sum(1 for i in all_items if i['urgency_status'] == 'overdue'),
        'urgent_count': sum(1 for i in all_items if i['urgency_status'] == 'urgent'),
        'missed_count': sum(1 for i in all_items if i['urgency_status'] == 'missed'),
    }
    return render(request, 'pages/deadlines.html', context)


@login_required
@require_POST
def deadline_mark_complete(request, event_id):
    """AJAX endpoint to mark a deadline as completed."""
    event = DeadlineService.mark_complete(request.user, event_id)

    if event is None:
        return JsonResponse({'error': 'Deadline not found.'}, status=404)

    return JsonResponse({
        'id': event.pk,
        'is_completed': True,
        'title': event.title,
    })