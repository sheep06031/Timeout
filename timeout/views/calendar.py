import calendar as cal
import json
import os
from datetime import timedelta, date, datetime, time
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from timeout.models import Event
from django.core.exceptions import ValidationError
from django.db.models import Q
from timeout.views.ai_workload import get_ai_workload_warning
from timeout.views.deadline_warning import get_deadline_study_warnings


@login_required
def calendar_view(request):
    """Renders a monthly calendar grid with events in day cells, including recurring events."""
    today = timezone.now().date()
    year, month = _parse_month_year(request, today)
    prev_year, prev_month, next_year, next_month = _calc_nav_months(year, month)
    weeks_raw = cal.Calendar(firstweekday=0).monthdatescalendar(year, month)
    last_visible = weeks_raw[-1][-1]

    events_qs = _fetch_calendar_events(request.user, last_visible)
    now_dt = timezone.now()
    events_by_date = _index_events_by_date(events_qs, last_visible, now_dt)
    weeks = _build_weeks_grid(weeks_raw, month, today, events_by_date)

    context = _build_calendar_context(
        request, weeks, year, month, prev_year, prev_month,
        next_year, next_month, events_qs, events_by_date,
    )
    return render(request, "pages/calendar.html", context)


def _parse_month_year(request, today):
    """Parse year and month from request query params with bounds clamping."""
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1
    return year, month


def _calc_nav_months(year, month):
    """Return (prev_year, prev_month, next_year, next_month) for calendar navigation."""
    if month > 1:
        prev_month, prev_year = month - 1, year
    else:
        prev_month, prev_year = 12, year - 1
    if month < 12:
        next_month, next_year = month + 1, year
    else:
        next_month, next_year = 1, year + 1
    return prev_year, prev_month, next_year, next_month


def _fetch_calendar_events(user, last_visible):
    """Fetch all events up to last_visible date for the user and global events."""
    last_visible_datetime = timezone.make_aware(
        datetime.combine(last_visible, time.max)
    )
    return Event.objects.filter(
        Q(creator=user) | Q(is_global=True),
        start_datetime__lte=last_visible_datetime,
    ).order_by("start_datetime")


def _build_event_data(ev, now_dt):
    """Build a dict representation of a single event for the calendar grid."""
    return {
        'id': ev.id,
        'title': ev.title,
        'start_datetime': ev.start_datetime,
        'end_datetime': ev.end_datetime,
        'event_type': ev.event_type,
        'event_type_display': ev.get_event_type_display(),
        'recurrence_display': ev.get_recurrence_display(),
        'location': ev.location,
        'description': ev.description,
        'is_all_day': ev.is_all_day,
        'visibility': ev.visibility,
        'allow_conflict': ev.allow_conflict,
        'color': getattr(ev, 'color', ''),
        'status_display': get_event_status(ev.start_datetime, ev.end_datetime, now_dt),
    }


def _build_recurrence_data(ev, current_date, now_dt):
    """Build a pseudo-event dict for a recurrence instance on a given date."""
    start_dt = timezone.make_aware(datetime.combine(current_date, ev.start_datetime.time()))
    end_dt = timezone.make_aware(datetime.combine(current_date, ev.end_datetime.time()))
    return {
        'original': ev,
        'recurrence_instance': True,
        'id': ev.id,
        'title': ev.title,
        'start_datetime': start_dt,
        'end_datetime': end_dt,
        'event_type': ev.event_type,
        'event_type_display': ev.get_event_type_display(),
        'recurrence_display': ev.get_recurrence_display(),
        'location': ev.location,
        'description': ev.description,
        'is_all_day': ev.is_all_day,
        'instance_date': current_date,
        'visibility': ev.visibility,
        'allow_conflict': ev.allow_conflict,
        'color': getattr(ev, 'color', ''),
        'status_display': get_event_status(start_dt, end_dt, now_dt),
    }


def _advance_recurrence_date(current_date, recurrence):
    """Advance a date by one recurrence interval. Returns None if invalid."""
    if recurrence == 'daily':
        return current_date + timedelta(days=1)
    if recurrence == 'weekly':
        return current_date + timedelta(weeks=1)
    if recurrence == 'monthly':
        month_num = current_date.month + 1
        year_num = current_date.year
        if month_num > 12:
            month_num = 1
            year_num += 1
        day_num = min(current_date.day, cal.monthrange(year_num, month_num)[1])
        return date(year_num, month_num, day_num)
    return None


def _expand_recurrences(ev, last_visible, now_dt, events_by_date):
    """Expand a recurring event into pseudo-event entries up to last_visible."""
    current_date = ev.start_datetime.date()
    while True:
        current_date = _advance_recurrence_date(current_date, ev.recurrence)
        if current_date is None or current_date > last_visible:
            break
        pseudo_event = _build_recurrence_data(ev, current_date, now_dt)
        events_by_date.setdefault(current_date, []).append(pseudo_event)


def _index_events_by_date(events_qs, last_visible, now_dt):
    """Index events by date, expanding recurrences into separate entries."""
    events_by_date = {}
    for ev in events_qs:
        event_data = _build_event_data(ev, now_dt)
        events_by_date.setdefault(ev.start_datetime.date(), []).append(event_data)
        if ev.recurrence != 'none':
            _expand_recurrences(ev, last_visible, now_dt, events_by_date)
    return events_by_date


def _build_weeks_grid(weeks_raw, month, today, events_by_date):
    """Build the weeks grid structure for the calendar template."""
    weeks = []
    for week in weeks_raw:
        days = [
            {
                "date": day,
                "day_num": day.day,
                "in_month": day.month == month,
                "is_today": day == today,
                "events": events_by_date.get(day, []),
            }
            for day in week
        ]
        weeks.append(days)
    return weeks


def _get_reschedule_prompts(user):
    """Return reschedule prompts for missed study sessions."""
    now = timezone.now()
    missed_sessions = Event.objects.filter(
        creator=user,
        event_type=Event.EventType.STUDY_SESSION,
        status=Event.EventStatus.UPCOMING,
        end_datetime__lt=now,
        is_completed=False,
    )
    return [
        {
            'id': e.pk,
            'title': e.title,
            'duration_minutes': int((e.end_datetime - e.start_datetime).total_seconds() / 60),
            'reason': 'missed',
        }
        for e in missed_sessions
    ]


def _build_calendar_context(request, weeks, year, month, prev_year, prev_month, next_year, next_month, events_qs, events_by_date):
    """Assemble the full context dict for the calendar template."""
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    today_events = events_by_date.get(timezone.now().date(), [])
    reschedule_prompts = _get_reschedule_prompts(request.user)
    reschedule_prompts += request.session.pop('reschedule_prompts', [])
    return {
        "weeks": weeks, "year": year, "month": month,
        "month_name": month_names[month],
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "workload_warning": get_ai_workload_warning(request.user, today_events),
        "upcoming_deadlines": Event.objects.filter(
            creator=request.user,
            event_type__in=[Event.EventType.DEADLINE, Event.EventType.EXAM],
            start_datetime__gte=timezone.now(),
        ).order_by('start_datetime')[:20],
        "reschedule_prompts": reschedule_prompts,
        "events": events_qs,
        "warnings": get_deadline_study_warnings(request.user),
    }


def get_event_status(start_dt, end_dt, now):
    """Return human-readable status string for an event."""
    if start_dt < now and end_dt > now:
        return 'Ongoing'
    elif end_dt < now:
        return 'Past'
    else:
        return 'Upcoming'


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
            event.start_datetime = s['start']
            event.end_datetime = s['end']
            event.save()
            updated += 1
        except (Event.DoesNotExist, KeyError):
            continue

    return JsonResponse({'success': True, 'count': updated})


@login_required
@require_POST
def subscribe_event(request, pk):
    """Subscribe to a public event by copying it to the user's calendar."""
    from django.shortcuts import get_object_or_404
    original = get_object_or_404(Event, pk=pk, visibility=Event.Visibility.PUBLIC)
    if original.creator == request.user:
        return JsonResponse({'success': False, 'error': 'You own this event.'}, status=400)
    already = Event.objects.filter(
        creator=request.user,
        title=original.title,
        start_datetime=original.start_datetime,
    ).exists()
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
        allow_conflict=True,
    )
    return JsonResponse({'success': True})


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


@login_required
@require_POST
def event_create(request):
    """Create a new calendar event from form POST data."""
    is_all_day = request.POST.get("is_all_day") == "on"
    allow_conflict = request.POST.get("allow_conflict") == "on"

    start_datetime, end_datetime = _parse_event_datetimes(request, is_all_day)
    if start_datetime is None:
        return redirect("calendar")

    event = Event(
        creator=request.user,
        title=request.POST["title"],
        event_type=request.POST.get("event_type", "other"),
        start_datetime=timezone.make_aware(
            datetime.fromisoformat(start_datetime)
        ),
        end_datetime=timezone.make_aware(
            datetime.fromisoformat(end_datetime)
        ),
        location=request.POST.get("location", ""),
        description=request.POST.get("description", ""),
        allow_conflict=allow_conflict,
        visibility=request.POST.get("visibility", "public"),
        is_all_day=is_all_day,
        recurrence=request.POST.get("recurrence", "none"),
    )

    try:
        event.full_clean()
        event.save()
        messages.success(request, f'"{event.title}" added to calendar.')
    except ValidationError as e:
        messages.error(request, '; '.join(e.messages))

    return redirect("calendar")
