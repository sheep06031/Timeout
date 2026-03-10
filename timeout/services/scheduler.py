"""
Scheduler Service — Gap-Finder Algorithm for weekly planning.

Place this file at: timeout/services/scheduler.py
Then add to timeout/services/__init__.py:
    from .scheduler import SchedulerService
"""

from datetime import datetime, timedelta, time, date
from django.utils import timezone
from django.db.models import Q
from timeout.models import Event
from timeout.services.estimation import EstimationService


# Configurable time window
DAY_START_HOUR = 9   # 9 AM
DAY_END_HOUR = 20    # 8 PM (20:00)
SLOT_DURATION = timedelta(hours=1)


class SchedulerService:
    """Plans the week by finding gaps in the user's schedule."""

    @staticmethod
    def get_week_bounds(reference_date=None):
        """
        Return (monday, sunday) for the week containing reference_date.
        Both are date objects.
        """
        if reference_date is None:
            reference_date = timezone.now().date()

        # Monday = 0, Sunday = 6
        monday = reference_date - timedelta(days=reference_date.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday

    @staticmethod
    def get_fixed_events(user, week_start, week_end):
        """
        Fetch all non-suggestion events for the user in the given week.
        These are 'Fixed' blocks that the scheduler cannot move.
        """
        start_dt = timezone.make_aware(datetime.combine(week_start, time.min))
        end_dt = timezone.make_aware(datetime.combine(week_end, time.max))

        return Event.objects.filter(
            Q(creator=user) | Q(is_global=True),
            is_suggestion=False,
            start_datetime__lt=end_dt,
            end_datetime__gt=start_dt,
        ).order_by('start_datetime')

    @staticmethod
    def build_slot_grid(week_start):
        """
        Build a list of hourly time slots for the week (Mon–Sun, 9 AM – 8 PM).
        Each slot is a dict: {date, start_time, end_time, start_dt, end_dt, status}
        """
        slots = []
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            for hour in range(DAY_START_HOUR, DAY_END_HOUR):
                slot_start = timezone.make_aware(
                    datetime.combine(current_date, time(hour, 0))
                )
                slot_end = slot_start + SLOT_DURATION
                slots.append({
                    'date': current_date,
                    'hour': hour,
                    'start_dt': slot_start,
                    'end_dt': slot_end,
                    'status': 'free',       # free | busy | suggested
                    'event': None,           # filled if busy
                    'suggestion': None,      # filled if suggested
                })
        return slots

    @staticmethod
    def mark_busy_slots(slots, fixed_events):
        """
        Mark slots as 'busy' if they overlap with any fixed event.
        Also attaches the event to the slot for display.
        """
        for slot in slots:
            for event in fixed_events:
                # Check overlap: event starts before slot ends AND event ends after slot starts
                if event.start_datetime < slot['end_dt'] and event.end_datetime > slot['start_dt']:
                    slot['status'] = 'busy'
                    slot['event'] = event
                    break  # one event per slot for display
        return slots

    @staticmethod
    def fill_suggestions(slots, user, target_hours=14):
        """
        Fill free slots with suggested study blocks until target_hours is reached.
        Uses the EstimationService to determine block size.

        Strategy: distribute blocks evenly across the week, preferring mornings.
        """
        estimated = EstimationService.get_estimated_hours(user, 'study_session')
        # Round up to nearest whole slot count
        slots_per_block = max(1, round(estimated))

        hours_remaining = target_hours
        now = timezone.now()

        # Group free slots by date for even distribution
        free_by_date = {}
        for slot in slots:
            if slot['status'] == 'free' and slot['start_dt'] > now:
                free_by_date.setdefault(slot['date'], []).append(slot)

        # Sort dates chronologically
        sorted_dates = sorted(free_by_date.keys())

        if not sorted_dates:
            return slots

        # Distribute target hours across available days
        hours_per_day = target_hours / len(sorted_dates)

        for current_date in sorted_dates:
            if hours_remaining <= 0:
                break

            day_budget = min(hours_per_day, hours_remaining)
            day_slots = free_by_date[current_date]

            # Find consecutive free slot runs
            i = 0
            while i < len(day_slots) and day_budget > 0:
                # Try to fill a block of slots_per_block consecutive slots
                block_size = min(slots_per_block, int(day_budget), len(day_slots) - i)

                # Check if slots are consecutive
                consecutive = True
                for j in range(1, block_size):
                    if day_slots[i + j]['hour'] != day_slots[i + j - 1]['hour'] + 1:
                        consecutive = False
                        break

                if consecutive and block_size > 0:
                    for j in range(block_size):
                        day_slots[i + j]['status'] = 'suggested'
                        day_slots[i + j]['suggestion'] = {
                            'title': 'Study Block',
                            'event_type': 'study_session',
                            'hours': 1,
                        }
                    hours_remaining -= block_size
                    day_budget -= block_size
                    i += block_size
                else:
                    i += 1

        return slots

    @staticmethod
    def plan_week(user, target_hours=14, reference_date=None):
        """
        Main entry point: plan the user's week.
        Returns the slot grid with busy and suggested blocks marked.
        """
        week_start, week_end = SchedulerService.get_week_bounds(reference_date)
        fixed_events = SchedulerService.get_fixed_events(user, week_start, week_end)
        slots = SchedulerService.build_slot_grid(week_start)
        slots = SchedulerService.mark_busy_slots(slots, fixed_events)
        slots = SchedulerService.fill_suggestions(slots, user, target_hours)

        return {
            'slots': slots,
            'week_start': week_start,
            'week_end': week_end,
            'fixed_events': fixed_events,
            'target_hours': target_hours,
        }

    @staticmethod
    def commit_suggestions(user, reference_date=None):
        """
        Convert all suggested blocks into real Event objects.
        First removes any existing suggestions for the week, then creates new ones.
        """
        week_start, week_end = SchedulerService.get_week_bounds(reference_date)

        # Remove old suggestions for this week
        start_dt = timezone.make_aware(datetime.combine(week_start, time.min))
        end_dt = timezone.make_aware(datetime.combine(week_end, time.max))

        Event.objects.filter(
            creator=user,
            is_suggestion=True,
            start_datetime__gte=start_dt,
            start_datetime__lte=end_dt,
        ).delete()

        # Re-run the planner to get fresh suggestions
        plan = SchedulerService.plan_week(user, reference_date=reference_date)
        created_events = []

        for slot in plan['slots']:
            if slot['status'] == 'suggested' and slot['suggestion']:
                event = Event.objects.create(
                    creator=user,
                    title=slot['suggestion']['title'],
                    event_type='study_session',
                    start_datetime=slot['start_dt'],
                    end_datetime=slot['end_dt'],
                    is_suggestion=True,
                    is_all_day=False,
                    visibility='private',
                    allow_conflict=True,
                    estimated_hours=1.0,
                )
                created_events.append(event)

        return created_events

    @staticmethod
    def clear_suggestions(user, reference_date=None):
        """Remove all AI-suggested blocks for the given week."""
        week_start, week_end = SchedulerService.get_week_bounds(reference_date)
        start_dt = timezone.make_aware(datetime.combine(week_start, time.min))
        end_dt = timezone.make_aware(datetime.combine(week_end, time.max))

        deleted_count, _ = Event.objects.filter(
            creator=user,
            is_suggestion=True,
            start_datetime__gte=start_dt,
            start_datetime__lte=end_dt,
        ).delete()

        return deleted_count