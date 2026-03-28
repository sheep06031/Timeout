"""
Views for managing deadlines, including listing, filtering, and marking deadlines as complete/incomplete. Accessible only to logged-in users.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from timeout.services.deadline_service import DeadlineService
from timeout.services.notification_service import NotificationService


def _parse_deadline_filters(request):
    """Parse and validate filter/sort params from the query string."""
    status_filter = request.GET.get('status', 'active')
    sort_order = request.GET.get('sort', 'asc')
    event_type = request.GET.get('type', '')
    if status_filter not in ('active', 'completed', 'all'):
        status_filter = 'active'
    if sort_order not in ('asc', 'desc'):
        sort_order = 'asc'
    valid_types = ('deadline', 'exam', 'class', 'meeting', 'study_session', 'other')
    if event_type and event_type not in valid_types:
        event_type = ''
    return status_filter, sort_order, event_type

@login_required
def deadline_list_view(request):
    """Renders the deadline list view showing deadlines with filter and sort options."""
    status_filter, sort_order, event_type = _parse_deadline_filters(request)
    deadlines = DeadlineService.get_filtered_deadlines(
        request.user,
        status_filter=status_filter,
        sort_order=sort_order,
        event_type=event_type or None,
    )
    NotificationService.create_deadline_notifications(request.user)
    context = build_context(request, deadlines, status_filter, sort_order, event_type)
    return render(request, 'pages/deadlines.html', context)


def build_context(request, deadlines, status_filter, sort_order, event_type):
    """Build context for the deadline list view, including counts and filter options."""
    return {
        'deadlines': deadlines,
        'total_count': len(deadlines),
        'overdue_count': sum(1 for d in deadlines if d['urgency_status'] == 'overdue'),
        'urgent_count': sum(1 for d in deadlines if d['urgency_status'] == 'urgent'),
        'completed_count': sum(1 for d in deadlines if d['urgency_status'] == 'completed'),
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

@login_required
@require_POST
def deadline_mark_incomplete(request, event_id):
    """AJAX endpoint to mark a deadline back to incomplete."""
    event = DeadlineService.mark_incomplete(request.user, event_id)

    if event is None:
        return JsonResponse({'error': 'Deadline not found.'}, status=404)

    return JsonResponse({
        'id': event.pk,
        'is_completed': False,
        'title': event.title,
    })
