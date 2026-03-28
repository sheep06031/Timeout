import calendar as cal
from datetime import timedelta, date, datetime, time
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from timeout.models import Event, DismissedAlert
from django.db.models import Q
from timeout.views.deadline_warning import get_deadline_study_warnings
from timeout.services import DeadlineService, AIService

MONTH_NAMES = [ 
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

@login_required
def calendar_view(request):
    """Renders a monthly calendar grid with events in day cells, including recurring events."""
    today = timezone.now().date() # get today's date for default
    year, month = check_month_year(*get_date(request, today)) 
    nav = get_months(year, month) # get previous and next month/year for navigation links

    cal_obj = cal.Calendar(firstweekday=0)
    weeks_raw = cal_obj.monthdatescalendar(year, month)
    last_visible = weeks_raw[-1][-1] 

    events_qs = visible_events(request.user, last_visible)
    events_by_date = index_events(events_qs, last_visible) 
    weeks = build_weeks(weeks_raw, month, today, events_by_date) 
    context = calendar_context(year, month, nav, weeks) 
    context.update(get_data(request, events_by_date)) 
    return render(request, "pages/calendar.html", context)

def calendar_context(year, month, nav, weeks):
    """Helper function to build the context dict for the calendar template"""
    prev_month, prev_year, next_month, next_year = nav 
    return {
        "weeks": weeks,
        "month": month,
        "year": year,
        "month_name": MONTH_NAMES[month],
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }

def get_date(request, today):
    """Helper function to parse through the month and year from url, fallaback to today"""
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month
    return year, month

def check_month_year(year, month):
    """Helper function to check that the months don't go below 1 or above 12
    Adjust the year accordingly"""
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1
    return year, month

def get_months(year, month):
    """Helper function to get previous and next months and years"""
    if month > 1:
        prev_month, prev_year = month - 1, year
    else:
        prev_month, prev_year = 12, year - 1
    if month < 12:
        next_month, next_year = month + 1, year
    else:
        next_month = 1
        next_year = year + 1
    return prev_month, prev_year, next_month, next_year

def visible_events(user, last_visible):
    """Helper function to fetch events for the visible date range, including recurring events"""
    last_day = timezone.make_aware(datetime.combine(last_visible, time.max)) 
    events_qs = Event.objects.filter( 
        Q(creator=user) | Q(is_global=True),
        start_datetime__lte=last_day,
    ).order_by("start_datetime")
    return events_qs # return the queryset

def index_events(events_qs, last_visible):
    """Helper function to index events by date
    Maps each date to a list of events as dicts """
    now_date = timezone.now()
    events_by_date = {} # dict to hold lists of events for each date
    for ev in events_qs:
        data = create_dict(ev, ev.start_datetime, ev.end_datetime, now_date) # create a consistent dict for the event
        events_by_date.setdefault(ev.start_datetime.date(), []).append(data) # add the event to the list for its start date

        if ev.recurrence != 'none':
            create_recurrence(ev, last_visible, now_date, events_by_date) 

    return events_by_date 

def create_dict(ev, start_dt, end_dt, now_date):
    """Helper function to create a dict for an event that can be used by template"""
    return {
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
        'visibility': ev.visibility,
        'allow_conflict': ev.allow_conflict,
        'color': getattr(ev, 'color', ''),
        'status_display': event_status(start_dt, end_dt, now_date),
    }

def create_recurrence(ev, last_visible, now_date, events_by_date):
    """Generate pseudo-event dicts for recurring occurrences within the visible range."""
    current_date = ev.start_datetime.date()

    while True:
        current_date = advance_date(current_date, ev.recurrence)
        if current_date is None or current_date > last_visible:
            break

        start_dt = timezone.make_aware(
            datetime.combine(current_date, ev.start_datetime.time()),
        )
        end_dt = timezone.make_aware(
            datetime.combine(current_date, ev.end_datetime.time()),
        )
        data = create_dict(ev, start_dt, end_dt, now_date)
        events_by_date.setdefault(current_date, []).append(data)

def advance_date(current_date, recurrence):
    """Return the next occurrence date. Returns None if the recurrence is not recognized."""
    if recurrence == 'daily':
        return current_date + timedelta(days=1)
    if recurrence == 'weekly':
        return current_date + timedelta(weeks=1)
    if recurrence == 'monthly':
        month_num = current_date.month + 1
        year_num = current_date.year
        if month_num > 12:
            month_num, year_num = 1, year_num + 1
        day_num = min(current_date.day, cal.monthrange(year_num, month_num)[1])
        return date(year_num, month_num, day_num)
    return None

def build_weeks(weeks_raw, month, today, events_by_date):
    """Helper function to convert raw weeks from calendar into a structure for the template"""
    return[
        [build_day(day, month, today, events_by_date) for day in week]
        for week in weeks_raw
    ]

def build_day(day, month, today, events_by_date):
    """Helper function to build a dict for each day in the calendar grid"""
    return {
        "date": day,
        "day_num": day.day,
        "in_month": day.month == month,
        "is_today": day == today,
        "events": events_by_date.get(day, []), # get events for this day
    }


def _get_workload_and_suggestions(user, events_by_date, now, dismissed_keys):
    """Return workload warning, its alert key, and AI suggestions."""
    today_str = now.date().isoformat()
    workload_key = f'workload_{user.id}_{today_str}'
    today_events = (events_by_date or {}).get(now.date(), [])
    raw_workload = AIService.get_workload_warning(user, today_events)
    workload_warning = raw_workload if raw_workload and workload_key not in dismissed_keys else None
    return workload_warning, workload_key, AIService.get_suggestions(user, today_events)


def get_data(request, events_by_date=None):
    """Helper function to gather data needed for upcoming deadlines and reschedule prompts"""
    now = timezone.now()
    dismissed_keys = set(DismissedAlert.objects.filter(
        user=request.user).values_list('alert_key', flat=True))
    upcoming_deadlines = DeadlineService.get_upcoming_deadlines(request.user, limit=20)
    all_warnings = get_deadline_study_warnings(request.user)
    warnings = [w for w in all_warnings if w['key'] not in dismissed_keys]
    workload_warning, workload_key, suggestions = _get_workload_and_suggestions(
        request.user, events_by_date, now, dismissed_keys)
    return {
        "upcoming_deadlines": upcoming_deadlines,
        "warnings": warnings,
        "workload_warning": workload_warning,
        "workload_alert_key": workload_key,
        "ai_suggestions": suggestions}

def event_status(start_dt, end_dt, now):
    """Helper function to derive a human-readable status"""
    if start_dt < now and end_dt > now:
        return 'Ongoing'
    elif end_dt < now:
        return 'Past'
    else:
        return 'Upcoming'