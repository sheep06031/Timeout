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
    weeks = []
    workload_warning = None

    # Get today's date from the URL query string if nothing is provided
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Get months from 1 to 12 
    if month < 1:
        month, year = 12, year - 1
    # Handle navigating backwards or forwards when going before january of after december
    elif month > 12:
        month, year = 1, year + 1

    # Wrapper to make sure if the months go further than 12 so it skips to the next year
    # Creates links for before or after the current month and year 
    if month > 1:
        prev_month = month - 1
        prev_year = year
    else:
        prev_month = 12
        prev_year = year - 1
    if month < 12:
        next_month = month + 1
        next_year = year
    else:
        next_month = 1
        next_year = year + 1

    # Build weeks grid starting from Monday
    cal_obj = cal.Calendar(firstweekday=0)
    weeks_raw = cal_obj.monthdatescalendar(year, month)

    # Determine visible range
    first_visible = weeks_raw[0][0]
    last_visible = weeks_raw[-1][-1]

    context = {
        "weeks": weeks,
        "month": month,
        "year": year,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "now": timezone.now(),
    }

    # Fetch events for visible date range
    lookahead_days = 365  # how far in the future you want to show recurring events
    last_visible_datetime = timezone.make_aware(
        datetime.combine(last_visible, time.max)
    )
    events_qs = Event.objects.filter(
        Q(creator=request.user) | Q(is_global=True),
        start_datetime__lte=last_visible_datetime,
    ).order_by("start_datetime")

    calendar_events = []
    for event in events_qs:
        if event.recurrence == "yearly" and event.is_global:
            # Create a display instance for this year
            event_start = event.start_datetime.replace(year=last_visible.year)
            event_end = event.end_datetime.replace(year=last_visible.year)
            calendar_events.append({
                "title": event.title,
                "description": event.description,
                "start_datetime": event_start,
                "end_datetime": event_end,
                "is_global": True,
                "visibility": event.visibility,
            })
        else:
            calendar_events.append(event)

    # Index events by date, including recurrence expansion
    now_dt = timezone.now()
    events_by_date = {}

    for ev in events_qs:
        # Build consistent dict for real event
        event_data = {
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
        events_by_date.setdefault(ev.start_datetime.date(), []).append(event_data)  # ← event_data not ev

        if ev.recurrence == 'none':
            continue

        current_date = ev.start_datetime.date()
        while True:
            if ev.recurrence == 'daily':
                current_date += timedelta(days=1)
            elif ev.recurrence == 'weekly':
                current_date += timedelta(weeks=1)
            elif ev.recurrence == 'monthly':
                month_num = current_date.month + 1
                year_num = current_date.year
                if month_num > 12:
                    month_num = 1
                    year_num += 1
                day_num = min(current_date.day, cal.monthrange(year_num, month_num)[1])
                current_date = date(year_num, month_num, day_num)
            else:
                break

            if current_date > last_visible:
                break

            start_dt = timezone.make_aware(datetime.combine(current_date, ev.start_datetime.time()))
            end_dt   = timezone.make_aware(datetime.combine(current_date, ev.end_datetime.time()))

            pseudo_event = {
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
            events_by_date.setdefault(current_date, []).append(pseudo_event)

    # Build weeks structure for template
    weeks = []
    
    for week in weeks_raw:
        days = []
        for day in week:
            days.append({
                "date": day,
                "day_num": day.day,
                "in_month": day.month == month,
                "is_today": day == today,
                "events": events_by_date.get(day, []),
            })
        weeks.append(days)

    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    # Get today's events for AI workload warning
    today_events = events_by_date.get(timezone.now().date(), [])
    workload_warning = get_ai_workload_warning(today_events)
    
    upcoming_deadlines = Event.objects.filter(
        creator=request.user,
        event_type__in=[Event.EventType.DEADLINE, Event.EventType.EXAM],
        start_datetime__gte=timezone.now(),
    ).order_by('start_datetime')[:20]
    
    # Missed study sessions: past events still in UPCOMING status
    now = timezone.now()
    missed_sessions = Event.objects.filter(
        creator=request.user,
        event_type=Event.EventType.STUDY_SESSION,
        status=Event.EventStatus.UPCOMING,
        end_datetime__lt=now,
    )
    reschedule_prompts = [
        {
            'id': e.pk,
            'title': e.title,
            'duration_minutes': int((e.end_datetime - e.start_datetime).total_seconds() / 60),
            'reason': 'missed',
        }
        for e in missed_sessions
    ]

    # Recently cancelled study sessions (stored in session after event_cancel view)
    reschedule_prompts += request.session.pop('reschedule_prompts', [])

    warnings = get_deadline_study_warnings(request.user)

    context = {
        "weeks": weeks,
        "year": year,
        "month": month,
        "month_name": month_names[month],
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "workload_warning": workload_warning,

        "upcoming_deadlines": upcoming_deadlines,
        "reschedule_prompts": reschedule_prompts,
        "events": events_qs,
        "warnings": warnings,
    }

    return render(request, "pages/calendar.html", context)

def get_event_status(start_dt, end_dt, now):
    if start_dt < now and end_dt > now:
        return 'Ongoing'
    elif end_dt < now:
        return 'Past'
    else:
        return 'Upcoming'

@login_required
@require_POST
def subscribe_event(request, pk):
    from django.shortcuts import get_object_or_404
    original = get_object_or_404(Event, pk=pk, visibility=Event.Visibility.PUBLIC)
    if original.creator == request.user:
        return JsonResponse({'success': False, 'error': 'You own this event.'}, status=400)
    already = Event.objects.filter(creator=request.user, title=original.title, start_datetime=original.start_datetime,
    ).exists()
    if already:
        return JsonResponse({'success': False, 'error': 'Already subscribed.'}, status=400)
    Event.objects.create( creator=request.user,title=original.title,
        event_type=original.event_type, start_datetime=original.start_datetime,
        end_datetime=original.end_datetime, location=original.location,
        description=original.description, visibility=Event.Visibility.PRIVATE,
        is_all_day=original.is_all_day, recurrence=original.recurrence,
        allow_conflict=True,
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def event_create(request):
    is_all_day = request.POST.get("is_all_day") == "on"
    #allow_conflict = request.POST.get("allow_conflict") == "on"

    start_datetime = request.POST.get("start_datetime")
    end_datetime = request.POST.get("end_datetime")
    recurrence = request.POST.get("recurrence", "none")  # default 'none'

    if is_all_day:
        if not start_datetime:
            messages.error(request, "Please select a date for an all-day event.")
            return redirect("calendar")
        date_part = start_datetime.split("T")[0]
        start_datetime = f"{date_part}T00:00"
        end_datetime = f"{date_part}T23:59"
    else:
        if not start_datetime or not end_datetime:
            messages.error(request, "Start and end times are required.")
            return redirect("calendar")

    event = Event(
        creator=request.user,
        title=request.POST["title"],
        event_type=request.POST.get("event_type", "other"),
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        location=request.POST.get("location", ""),
        description=request.POST.get("description", ""),
        #allow_conflict=allow_conflict,
        visibility=request.POST.get("visibility", "public"),
        is_all_day=is_all_day,
        recurrence=recurrence,
    )

    try:
        event.full_clean()
        event.save()
        messages.success(request, f'"{event.title}" added to calendar.')
    except ValidationError as e:
        messages.error(request, '; '.join(e.messages))

    return redirect("calendar")