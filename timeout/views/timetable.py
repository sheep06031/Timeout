"""
Timetable Views — Weekly hourly grid with AI suggestions.

Place this file at: timeout/views/timetable.py
"""

from datetime import timedelta, datetime, time
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from timeout.services.scheduler import SchedulerService
from timeout.services.estimation import EstimationService


@login_required
def timetable_view(request):
    """
    Renders the weekly hourly timetable with fixed events and AI suggestions.
    """
    today = timezone.now().date()

    # Parse week offset from query params (for week navigation)
    try:
        week_offset = int(request.GET.get('week', 0))
    except (ValueError, TypeError):
        week_offset = 0

    reference_date = today + timedelta(weeks=week_offset)

    # Parse target hours (default 14)
    try:
        target_hours = int(request.GET.get('hours', 14))
        target_hours = max(1, min(target_hours, 40))  # clamp 1–40
    except (ValueError, TypeError):
        target_hours = 14

    # Run the scheduler
    plan = SchedulerService.plan_week(
        request.user,
        target_hours=target_hours,
        reference_date=reference_date,
    )

    # Get estimation data for display
    estimates = EstimationService.get_all_estimates(request.user)

    # Build the grid structure for the template
    # Organize slots into a 2D structure: rows (hours) × columns (days)
    week_start = plan['week_start']
    week_end = plan['week_end']

    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        days.append({
            'date': d,
            'name': d.strftime('%a'),
            'day_num': d.day,
            'month_abbr': d.strftime('%b'),
            'is_today': d == today,
        })

    hours = list(range(9, 21))  # 9 AM to 8 PM

    # Build grid: dict keyed by (day_index, hour) -> slot
    grid = {}
    for slot in plan['slots']:
        day_index = (slot['date'] - week_start).days
        grid[(day_index, slot['hour'])] = slot

    # Build rows for template iteration
    rows = []
    for hour in hours:
        row = {
            'hour': hour,
            'label': f"{hour}:00" if hour >= 10 else f"0{hour}:00",
            'label_12h': _format_hour_12(hour),
            'cells': [],
        }
        for day_idx in range(7):
            slot = grid.get((day_idx, hour), {
                'status': 'free', 'event': None, 'suggestion': None
            })
            row['cells'].append(slot)
        rows.append(row)

    # Count stats
    suggested_count = sum(1 for s in plan['slots'] if s['status'] == 'suggested')
    busy_count = sum(1 for s in plan['slots'] if s['status'] == 'busy')
    free_count = sum(1 for s in plan['slots'] if s['status'] == 'free')

    context = {
        'days': days,
        'rows': rows,
        'hours': hours,
        'week_start': week_start,
        'week_end': week_end,
        'target_hours': target_hours,
        'suggested_hours': suggested_count,
        'busy_hours': busy_count,
        'free_hours': free_count,
        'estimates': estimates,
        'week_offset': week_offset,
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1,
    }

    return render(request, 'pages/timetable.html', context)


@login_required
@require_POST
def commit_plan(request):
    """
    AJAX endpoint: convert all suggested blocks into real events.
    """
    try:
        week_offset = int(request.POST.get('week', 0))
    except (ValueError, TypeError):
        week_offset = 0

    reference_date = timezone.now().date() + timedelta(weeks=week_offset)

    try:
        target_hours = int(request.POST.get('hours', 14))
    except (ValueError, TypeError):
        target_hours = 14

    created = SchedulerService.commit_suggestions(
        request.user, reference_date=reference_date
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'created_count': len(created),
            'message': f'{len(created)} study blocks added to your calendar.',
        })

    messages.success(request, f'{len(created)} study blocks added to your calendar.')
    return redirect(f'/timetable/?week={week_offset}&hours={target_hours}')


@login_required
@require_POST
def clear_plan(request):
    """
    AJAX endpoint: remove all AI-suggested blocks for the current week.
    """
    try:
        week_offset = int(request.POST.get('week', 0))
    except (ValueError, TypeError):
        week_offset = 0

    reference_date = timezone.now().date() + timedelta(weeks=week_offset)
    deleted = SchedulerService.clear_suggestions(
        request.user, reference_date=reference_date
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'deleted_count': deleted,
            'message': f'{deleted} suggested blocks removed.',
        })

    messages.success(request, f'{deleted} suggested blocks removed.')

    try:
        target_hours = int(request.POST.get('hours', 14))
    except (ValueError, TypeError):
        target_hours = 14

    return redirect(f'/timetable/?week={week_offset}&hours={target_hours}')


def _format_hour_12(hour):
    """Convert 24h hour to 12h format string."""
    if hour == 0:
        return '12 AM'
    elif hour < 12:
        return f'{hour} AM'
    elif hour == 12:
        return '12 PM'
    else:
        return f'{hour - 12} PM'