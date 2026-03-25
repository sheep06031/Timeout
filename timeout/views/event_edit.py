from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from timeout.models import Event
from datetime import datetime
from django.utils import timezone


def _handle_event_edit_post(request, event):
    """Apply POST data to event fields and save."""
    try:
        start_dt = timezone.make_aware(
            datetime.fromisoformat(request.POST.get("start_datetime"))
        )
        end_dt = timezone.make_aware(
            datetime.fromisoformat(request.POST.get("end_datetime"))
        )
    except (ValueError, TypeError):
        messages.error(request, "Invalid date/time format.")
        return redirect("calendar")

    event.title = request.POST.get("title") or event.title
    event.event_type = request.POST.get("event_type") or event.event_type
    event.visibility = request.POST.get("visibility") or event.visibility
    event.recurrence = request.POST.get("recurrence") or "none"
    event.start_datetime = start_dt
    event.end_datetime = end_dt
    event.location = request.POST.get("location")
    event.description = request.POST.get("description")
    event.allow_conflict = bool(request.POST.get("allow_conflict"))
    event.save()

    if event.event_type == Event.EventType.DEADLINE:
        session_ids = request.POST.getlist("linked_study_sessions")
        event.linked_study_sessions.set(session_ids)

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
