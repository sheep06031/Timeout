from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from timeout.services.deadline_service import DeadlineService


@login_required
def deadline_list_view(request):
    """Renders the deadline list view showing all active (incomplete) deadlines."""
    deadlines = DeadlineService.get_active_deadlines(request.user)

    context = {
        'deadlines': deadlines,
        'total_count': len(deadlines),
        'overdue_count': sum(1 for d in deadlines if d['urgency_status'] == 'overdue'), # Get how much assignments are overdue
        # Get how much assignments are urgent
        'urgent_count': sum(1 for d in deadlines if d['urgency_status'] == 'urgent'),
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