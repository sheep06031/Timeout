from timeout.models import Event
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

@login_required
def event_details(request, event_id):
    """View to display details of a specific event."""
    event = get_object_or_404(Event, id=event_id, creator=request.user)
    context = {
        'event': event,
        'is_past': event.is_past,
        'is_ongoing': event.is_ongoing,
        'is_upcoming': event.is_upcoming
    }
    return render(request, 'pages/event_details.html', {"event": event})