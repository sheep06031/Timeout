from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from timeout.models import Event, FocusSession


def get_user_events(user):
    """Return all events belonging to the given user."""
    return Event.objects.filter(creator=user)


def count_by_type(events):
    """Return a dict mapping each event type label to its count."""
    counts = {label: 0 for _, label in Event.EventType.choices}
    for event in events:
        label = Event.EventType(event.event_type).label
        counts[label] += 1
    return counts


def events_last_n_weeks(events, n=8):
    """Return weekly event counts for the last n weeks, oldest first."""
    now = timezone.now()
    weeks = []
    for i in range(n - 1, -1, -1):
        week_start = now - timezone.timedelta(weeks=i + 1)
        week_end = now - timezone.timedelta(weeks=i)
        count = events.filter(
            start_datetime__gte=week_start,
            start_datetime__lt=week_end,
        ).count()
        weeks.append({'label': week_start.strftime('%d %b'), 'count': count})
    return weeks


def events_last_n_months(events, n=6):
    """Return monthly event counts for the last n months, oldest first."""
    now = timezone.now()
    months = []
    for i in range(n - 1, -1, -1):
        month = (now.month - i - 1) % 12 + 1
        year = now.year - ((now.month - i - 1) // 12)
        count = events.filter(
            start_datetime__year=year,
            start_datetime__month=month,
        ).count()
        months.append({'label': timezone.datetime(year, month, 1).strftime('%b %Y'), 'count': count})
    return months


def get_urgent_events(events):
    """Return deadline and exam events due within the next 7 days."""
    now = timezone.now()
    soon = now + timezone.timedelta(days=7)
    urgent_types = [Event.EventType.DEADLINE, Event.EventType.EXAM]
    return events.filter(
        event_type__in=urgent_types,
        start_datetime__gte=now,
        start_datetime__lte=soon,
    ).order_by('start_datetime')


def _fmt(s):
    h, m = divmod(s, 3600)
    m = m // 60
    return f"{h}h {m}m" if h else f"{m}m"


def get_focus_stats(user):
    """Return focus session stats for the last 7 days."""
    week_start = timezone.now() - timezone.timedelta(days=7)
    sessions = FocusSession.objects.filter(user=user, started_at__gte=week_start)
    total_seconds = sessions.aggregate(total=Sum('duration_seconds'))['total'] or 0
    days_with_sessions = sessions.values('started_at__date').distinct().count()
    avg_seconds = total_seconds // days_with_sessions if days_with_sessions else 0

    today = timezone.localtime(timezone.now()).date()
    daily = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        day_seconds = sessions.filter(
            started_at__date=day
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        daily.append({
            'label': day.strftime('%a'),
            'date': day.day,
            'duration': _fmt(day_seconds) if day_seconds else '—',
            'seconds': day_seconds,
            'is_today': i == 0,
        })

    max_seconds = max((d['seconds'] for d in daily), default=0) or 1

    return {
        'focus_total': _fmt(total_seconds),
        'focus_avg': _fmt(avg_seconds),
        'focus_sessions_count': sessions.count(),
        'focus_daily': daily,
        'focus_max_seconds': max_seconds,
    }


def get_friend_focus_leaderboard(user):
    """Return this week's focus leaderboard for the user + people they follow."""
    week_start = timezone.now() - timezone.timedelta(days=7)
    candidates = list(user.following.all()) + [user]

    leaderboard = []
    for u in candidates:
        total = FocusSession.objects.filter(
            user=u,
            started_at__gte=week_start,
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        leaderboard.append({
            'user': u,
            'seconds': total,
            'duration': _fmt(total) if total else '—',
            'is_self': u.pk == user.pk,
        })

    leaderboard.sort(key=lambda x: x['seconds'], reverse=True)
    return leaderboard


def build_context(user):
    """Assemble all statistics data into a context dict."""
    events = get_user_events(user)
    urgent = get_urgent_events(events)
    weekly = events_last_n_weeks(events)
    return {
        'total_events': events.count(),
        'type_counts': count_by_type(events),
        'weekly_data': events_last_n_weeks(events),
        'this_week_count': weekly[-1]['count'] if weekly else 0,
        'monthly_data': events_last_n_months(events),
        'urgent_events': urgent,
        'urgent_count': urgent.count(),
        **get_focus_stats(user),
        'friend_leaderboard': get_friend_focus_leaderboard(user),
    }


@login_required
def statistics_view(request):
    """Render the statistics page for the logged-in user."""
    context = build_context(request.user)
    return render(request, 'timeout/statistics.html', context)