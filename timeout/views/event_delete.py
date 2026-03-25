from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from timeout.models import Event
from timeout.models.notification import Notification

@login_required
def event_delete(request, pk):
    """Delete an event and redirect to calendar."""
    event = get_object_or_404(Event, pk=pk, creator=request.user)
    title = event.title

    # Delete all known related objects first
    Notification.objects.filter(deadline=event).delete()

    # Delete any posts linked to this event
    try:
        event.posts.all().delete()
    except Exception:
        pass

    with connection.cursor() as cursor:
        cursor.execute('PRAGMA foreign_keys = OFF;')
    
    event.delete()

    with connection.cursor() as cursor:
        cursor.execute('PRAGMA foreign_keys = ON;')

    messages.success(request, f'Event "{title}" has been deleted.')
    return redirect('calendar')