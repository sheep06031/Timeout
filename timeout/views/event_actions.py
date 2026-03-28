import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from timeout.models import DismissedAlert, Event
from timeout.services import EventService
from timeout.utils import parse_aware_dt


def _parse_event_datetimes(request, is_all_day):
    """Parse and validate start/end datetimes from POST data."""
    start_datetime = request.POST.get("start_datetime")
    end_datetime = request.POST.get("end_datetime")

    if is_all_day:
        if not start_datetime:
            messages.error(request, "Please select a date for an all-day event.")
            return None, None
        date_part = start_datetime.split("T")[0]
        return f"{date_part}T00:00", f"{date_part}T23:59"

    if not start_datetime or not end_datetime:
        messages.error(request, "Start and end times are required.")
        return None, None

    return start_datetime, end_datetime


def _build_event_from_post(request, start_datetime, end_datetime, is_all_day):
    """Construct an Event from POST data and parsed datetimes."""
    return EventService.build_from_data(request.user, {
        'title': request.POST["title"],
        'event_type': request.POST.get("event_type", "other"),
        'start_datetime': parse_aware_dt(start_datetime),
        'end_datetime': parse_aware_dt(end_datetime),
        'location': request.POST.get("location", ""),
        'description': request.POST.get("description", ""),
        'visibility': request.POST.get("visibility", "public"),
        'is_all_day': is_all_day,
        'recurrence': request.POST.get("recurrence", "none"),
    })


@login_required
@require_POST
def event_create(request):
    """Create a new calendar event from form POST data."""
    is_all_day = request.POST.get("is_all_day") == "on"
    start_datetime, end_datetime = _parse_event_datetimes(request, is_all_day)
    if start_datetime is None:
        return redirect("calendar")
    event = _build_event_from_post(request, start_datetime, end_datetime, is_all_day)
    try:
        event.full_clean()
        event.save()
        messages.success(request, f'"{event.title}" added to calendar.')
    except ValidationError as e:
        messages.error(request, '; '.join(e.messages))
    return redirect("calendar")


@login_required
@require_POST
def subscribe_event(request, pk):
    """Subscribe to a public event by creating a private copy for the user."""
    original = get_object_or_404(Event, pk=pk, visibility=Event.Visibility.PUBLIC)
    if original.creator == request.user:
        return JsonResponse({'success': False, 'error': 'You own this event.'}, status=400)
    already = Event.objects.filter(
        creator=request.user,
        title=original.title,
        start_datetime=original.start_datetime).exists()
    if already:
        return JsonResponse({'success': False, 'error': 'Already subscribed.'}, status=400)
    Event.objects.create(
        creator=request.user,
        title=original.title,
        event_type=original.event_type,
        start_datetime=original.start_datetime,
        end_datetime=original.end_datetime,
        location=original.location,
        description=original.description,
        visibility=Event.Visibility.PRIVATE,
        is_all_day=original.is_all_day,
        recurrence=original.recurrence,
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def apply_session_schedule(request):
    """Bulk-update study session times after AI reschedule confirmation."""
    try:
        sessions = json.loads(request.POST.get('sessions', '[]'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid data.'}, status=400)

    updated = 0
    for s in sessions:
        try:
            event = Event.objects.get(
                pk=s['id'],
                creator=request.user,
                event_type=Event.EventType.STUDY_SESSION,
            )
            event.start_datetime = parse_aware_dt(s['start'])
            event.end_datetime = parse_aware_dt(s['end'])
            event.save()
            updated += 1
        except (Event.DoesNotExist, KeyError):
            continue

    return JsonResponse({'success': True, 'count': updated})


@login_required
@require_POST
def dismiss_alert(request):
    """Dismiss a dismissible alert by its key."""
    key = request.POST.get('key', '').strip()
    if not key:
        return JsonResponse({'success': False}, status=400)
    DismissedAlert.objects.get_or_create(user=request.user, alert_key=key)
    return JsonResponse({'success': True})
