from datetime import timedelta
from timeout.models import Event


def get_busy_slots(user, start, end):
    events = Event.objects.filter(
        creator=user,
        start_datetime__lt=end,
        end_datetime__gt=start,
    ).order_by('start_datetime')
    return [(e.start_datetime, e.end_datetime) for e in events]


def get_free_slots(user, start, end, min_hours):
    """Return list of free slot dicts within 8am–10pm each day."""
    busy = get_busy_slots(user, start, end)
    free = []
    day = start.replace(hour=8, minute=0, second=0, microsecond=0)
    if day < start:
        day += timedelta(days=1)

    while day.date() <= end.date():
        day_end = day.replace(hour=22, minute=0)
        free.extend(_day_slots(day, day_end, busy, min_hours))
        day = (day + timedelta(days=1)).replace(hour=8, minute=0)

    return free


def pick_evenly_spaced_slots(free_slots, num_sessions, start, end):
    """Pick exactly num_sessions slots evenly distributed across the period."""
    if not free_slots or num_sessions <= 0:
        return free_slots

    total_days = (end.date() - start.date()).days or 1
    interval = total_days / num_sessions

    # Group slots by date for fast lookup
    by_date = {}
    for slot in free_slots:
        d = slot['start'][:10]
        by_date.setdefault(d, []).append(slot)

    chosen = []
    for i in range(num_sessions):
        # Target day index for this session (centre of each interval)
        target_offset = interval * (i + 0.5)
        target_date = (start + timedelta(days=target_offset)).date()

        # Search outward from target date for a free slot
        slot = _nearest_slot(by_date, target_date, end.date())
        if slot:
            # Remove used date so we don't double-book
            d = slot['start'][:10]
            by_date.pop(d, None)
            chosen.append(slot)

    return chosen if chosen else free_slots[:num_sessions]


def _nearest_slot(by_date, target, deadline):
    """Return the closest free slot to target date, searching outward."""
    from datetime import date, timedelta as td
    for offset in range(0, 60):
        for delta in ([td(days=-offset), td(days=offset)] if offset else [td(0)]):
            candidate = target + delta
            if candidate > deadline:
                continue
            key = candidate.isoformat()
            if key in by_date and by_date[key]:
                return by_date[key][0]
    return None


def _day_slots(day_start, day_end, busy, min_hours):
    """Find free gaps within a single day."""
    slots = []
    cursor = day_start
    min_gap = timedelta(hours=min_hours)

    for b_start, b_end in busy:
        if b_start >= day_end or b_end <= day_start:
            continue
        if cursor < b_start and (b_start - cursor) >= min_gap:
            slots.append({
                'start': cursor.strftime('%Y-%m-%dT%H:%M'),
                'end': b_start.strftime('%Y-%m-%dT%H:%M'),
            })
        if b_end > cursor:
            cursor = b_end

    if cursor < day_end and (day_end - cursor) >= min_gap:
        slots.append({
            'start': cursor.strftime('%Y-%m-%dT%H:%M'),
            'end': day_end.strftime('%Y-%m-%dT%H:%M'),
        })

    return slots
