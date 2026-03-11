from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from timeout.models import Event


@login_required
@require_POST
def event_cancel(request, pk):
    """Mark an event as cancelled. If it's a study session, queue a reschedule prompt."""
    event = get_object_or_404(Event, pk=pk, creator=request.user)

    event.status = Event.EventStatus.CANCELLED
    event.save(update_fields=['status'])

    if event.event_type == Event.EventType.STUDY_SESSION:
        duration_minutes = int((event.end_datetime - event.start_datetime).total_seconds() / 60)
        prompts = request.session.get('reschedule_prompts', [])
        prompts.append({
            'id': event.pk,
            'title': event.title,
            'duration_minutes': duration_minutes,
            'reason': 'cancelled',
        })
        request.session['reschedule_prompts'] = prompts

    return redirect('calendar')
