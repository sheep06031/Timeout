from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from timeout.models import Event

@login_required
def event_delete(request, pk):
    """Delete an event and redirect to calendar."""
    event = get_object_or_404(Event, pk=pk, creator=request.user)
    title = event.title
    event.delete()
    messages.success(request, f'Event "{title}" has been deleted.')
    return redirect('calendar')