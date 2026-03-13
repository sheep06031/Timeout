from django.utils import timezone
from timeout.models import Event


class DeadlineService:
    """Service for deadline list view query logic."""

    @staticmethod
    def get_active_deadlines(user):
        """
        Get all incomplete deadline events for a user
        Sort the upcoming deadline first
        Return a list of dicts with the event with fields: how urgent, time left and how much time has passed since beginning
        urgency_status, time_remaining, time_elapsed.
        """
        if not user.is_authenticated:
            return []
        
        # Get all deadline that are still remaning
        deadlines = Event.objects.filter(
            creator=user,
            event_type=Event.EventType.DEADLINE,
            is_completed=False,
        ).order_by('start_datetime')

        now = timezone.now()
        results = []

        #Calculate the remaining time for a deadline and time passed
        for event in deadlines:
            time_remaining = event.end_datetime - now
            time_elapsed = now - event.created_at

            # Determine urgency based on time remaining
            remaining_seconds = time_remaining.total_seconds()
            if remaining_seconds < 0:
                urgency_status = 'overdue'
            elif remaining_seconds <= 86400:  # 24 hours or less left is urgent
                urgency_status = 'urgent'
            else: # else normal
                urgency_status = 'normal'

            # Retirn the event as a dict with calculated values
            results.append({
                'event': event,
                'urgency_status': urgency_status,
                'time_remaining': time_remaining,
                'time_remaining_display': _format_timedelta(time_remaining),
                'time_elapsed_display': _format_elapsed(time_elapsed),
            })

        return results

    @staticmethod
    def get_filtered_deadlines(user, status_filter='active', sort_order='asc', event_type=None):
        """
        Get deadlines with filtering and sorting options.

        status_filter: 'active' (default) | 'completed' | 'all'
        sort_order:    'asc' (oldest first, default) | 'desc' (newest first)
        event_type:    None (all types) | 'deadline' | 'exam' | 'class' | etc.
        """
        if not user.is_authenticated:
            return []

        qs = Event.objects.filter(
            creator=user,
        )

        # Filter by event type if specified, otherwise show all
        if event_type:
            qs = qs.filter(event_type=event_type)

        if status_filter == 'active':
            qs = qs.filter(is_completed=False)
        elif status_filter == 'completed':
            qs = qs.filter(is_completed=True)
        # 'all' → no extra filter

        ordering = 'end_datetime' if sort_order == 'asc' else '-end_datetime'
        qs = qs.order_by(ordering)

        now = timezone.now()
        results = []

        for event in qs:
            time_remaining = event.end_datetime - now
            time_elapsed = now - event.created_at

            remaining_seconds = time_remaining.total_seconds()
            if event.is_completed:
                urgency_status = 'completed'
            elif remaining_seconds < 0:
                urgency_status = 'overdue'
            elif remaining_seconds <= 86400:
                urgency_status = 'urgent'
            else:
                urgency_status = 'normal'

            results.append({
                'event': event,
                'urgency_status': urgency_status,
                'time_remaining': time_remaining,
                'time_remaining_display': _format_timedelta(time_remaining),
                'time_elapsed_display': _format_elapsed(time_elapsed),
            })

        return results

    @staticmethod
    def mark_complete(user, event_id):
        """Mark any event as completed (not just deadlines)."""
        try:
            event = Event.objects.get(
                pk=event_id,
                creator=user,
                event_type=Event.EventType.DEADLINE,
                is_completed=False,
            )
            event.is_completed = True
            event.save(update_fields=['is_completed', 'updated_at'])
            return event
        except Event.DoesNotExist:
            return None

    @staticmethod
    def get_all_active_events(user):
        """
        Return all non-completed, non-cancelled user events grouped by type.
        Result: dict keyed by event_type string, values are lists of enriched item dicts.
        - deadline: all incomplete regardless of date
        - study_session: upcoming + past-but-uncompleted (so missed ones are visible)
        - exam/class/meeting/other: upcoming only
        """
        if not user.is_authenticated:
            return {}

        now = timezone.now()

        # Build a Q filter per type
        from django.db.models import Q
        qs = Event.objects.filter(
            creator=user,
            is_completed=False,
        ).exclude(status=Event.EventStatus.CANCELLED).filter(
            Q(event_type=Event.EventType.DEADLINE) |
            Q(event_type=Event.EventType.STUDY_SESSION) |
            Q(event_type__in=[
                Event.EventType.EXAM,
                Event.EventType.CLASS,
                Event.EventType.MEETING,
                Event.EventType.OTHER,
            ], end_datetime__gte=now)
        ).order_by('start_datetime')

        events_by_type = {}
        for event in qs:
            time_remaining = event.end_datetime - now
            time_elapsed = now - event.created_at
            remaining_seconds = time_remaining.total_seconds()

            if event.event_type == Event.EventType.DEADLINE:
                if remaining_seconds < 0:
                    urgency_status = 'overdue'
                elif remaining_seconds <= 86400:
                    urgency_status = 'urgent'
                else:
                    urgency_status = 'normal'
            else:
                urgency_status = 'missed' if remaining_seconds < 0 else 'upcoming'

            item = {
                'event': event,
                'urgency_status': urgency_status,
                'time_remaining': time_remaining,
                'time_remaining_display': _format_timedelta(time_remaining),
                'time_elapsed_display': _format_elapsed(time_elapsed),
            }
            events_by_type.setdefault(event.event_type, []).append(item)

        return events_by_type

# Function to create a human readable string for the reamining time
def _format_timedelta(td):
    """Calculation for time left."""
    """ Formatting to make it human readable for how much time has left in terms of days and hours"""
    total_seconds = int(td.total_seconds())

    # Python calculations to show if an event is overdue, and show how much time passed
    if total_seconds < 0:
        total_seconds = abs(total_seconds) # Turn number positive to calculate
        days, remainder = divmod(total_seconds, 86400) # divide by 86400 to find how many days and get remainder
        hours, remainder = divmod(remainder, 3600) # divide the remainder by 3600 to fund housr and get the remainder for minutes
        minutes = remainder // 60 # divide the remainder by 60 to find how many minutes
        if days > 0:
            return f"{days}d {hours}h overdue"
        if hours > 0:
            return f"{hours}h {minutes}m overdue"
        return f"{minutes}m overdue"
    
    # If not overdue calculate how much time is left
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h left"
    if hours > 0:
        return f"{hours}h {minutes}m left"
    return f"{minutes}m left"

# Calculation
def _format_elapsed(td):
    """ Calculation for time passed since creation as 'Added x ago'."""
    """ same as before formatting to make it human readable on the page"""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "Added just now"

    days = total_seconds // 86400 # 86400 seconds in one day
    if days > 0:
        return f"Added {days} day{'s' if days != 1 else ''} ago"

    hours = total_seconds // 3600 # 3600 seconds in one hour
    if hours > 0:
        return f"Added {hours} hour{'s' if hours != 1 else ''} ago"

    minutes = total_seconds // 60
    if minutes > 0:
        return f"Added {minutes} min ago"

    return "Added just now"