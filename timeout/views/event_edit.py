"""
View for editing an existing event. Handles both GET (show form) and POST (process form submission) requests. Includes helper functions to parse datetimes and apply form data to the event model.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from timeout.models import Event
from timeout.utils import parse_aware_dt


def _parse_event_datetimes(request):
    """Parse start/end datetimes from POST. Returns (start_dt, end_dt) or None on error."""
    try:
        start_dt = parse_aware_dt(request.POST.get("start_datetime"))
        end_dt = parse_aware_dt(request.POST.get("end_datetime"))
        return start_dt, end_dt
    except (ValueError, TypeError):
        messages.error(request, "Invalid date/time format.")
        return None


def _apply_event_fields(event, post_data, start_dt, end_dt):
    """Update event model fields from POST data and save."""
    event.title = post_data.get("title") or event.title
    event.event_type = post_data.get("event_type") or event.event_type
    event.visibility = post_data.get("visibility") or event.visibility
    event.recurrence = post_data.get("recurrence") or "none"
    event.start_datetime = start_dt
    event.end_datetime = end_dt
    event.location = post_data.get("location")
    event.description = post_data.get("description")
    event.save()
    if event.event_type == Event.EventType.DEADLINE:
        event.linked_study_sessions.set(post_data.getlist("linked_study_sessions"))


def _handle_event_edit_post(request, event):
    """Apply POST data to event fields and save."""
    result = _parse_event_datetimes(request)
    if result is None:
        return redirect("calendar")
    _apply_event_fields(event, request.POST, *result)
    return redirect("calendar")


@login_required
def event_edit(request, pk):
    """Edit an existing event via form."""
    event = get_object_or_404(Event, pk=pk, creator=request.user)
    study_sessions = Event.objects.filter(
        creator=request.user,
        event_type=Event.EventType.STUDY_SESSION,
        start_datetime__lt=event.start_datetime,
    )

    if request.method == "POST":
        return _handle_event_edit_post(request, event)

    return render(request, "pages/event_form.html", {
        "event": event,
        "study_sessions": study_sessions,
    })
