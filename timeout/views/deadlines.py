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
    """Renders the deadline list view showing deadlines with filter and sort options."""
    # Read filter/sort from query params with sensible defaults
    status_filter = request.GET.get('status', 'active')   # active | completed | all
    sort_order = request.GET.get('sort', 'asc')            # asc | desc
    event_type = request.GET.get('type', '')               # '' (all) | deadline | exam | ...

    # Validate inputs to prevent bad values
    if status_filter not in ('active', 'completed', 'all'):
        status_filter = 'active'
    if sort_order not in ('asc', 'desc'):
        sort_order = 'asc'

    valid_types = ('deadline', 'exam', 'class', 'meeting', 'study_session', 'other')
    if event_type and event_type not in valid_types:
        event_type = ''

    deadlines = DeadlineService.get_filtered_deadlines(
        request.user,
        status_filter=status_filter,
        sort_order=sort_order,
        event_type=event_type or None,
    )

    NotificationService.create_deadline_notifications(request.user)

    context = {
        'deadlines': deadlines,
        'total_count': len(deadlines),
        'overdue_count': sum(1 for d in deadlines if d['urgency_status'] == 'overdue'),
        'urgent_count': sum(1 for d in deadlines if d['urgency_status'] == 'urgent'),
        'completed_count': sum(1 for d in deadlines if d['urgency_status'] == 'completed'),
        # Pass current filter/sort back so the template can highlight active controls
        'status_filter': status_filter,
        'sort_order': sort_order,
        'event_type': event_type,
        'event_types': [
            ('', 'All Types'),
            ('deadline', 'Deadlines'),
            ('exam', 'Exams'),
            ('class', 'Classes'),
            ('meeting', 'Meetings'),
            ('study_session', 'Study Sessions'),
            ('other', 'Other'),
        ],
        'unread_notifications': request.user.notifications.filter(is_read=False),
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