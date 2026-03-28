"""
deadline_service.py - Defines DeadlineService for retrieving and filtering user deadlines,
marking them complete or incomplete, and computing urgency labels and time-remaining strings.
"""


from django.utils import timezone
from timeout.models import Event, user
from django.db.models import Q


class DeadlineService:
    """Service to help for deadline list view
    Provides calculations for time remainig, time elapsed and urgency for the deadlines
    Gets them in a human readabke format from time delta function"""

    @staticmethod
    def get_active_deadlines(user):
        """Get all active events, ordered by the closest deadline.
        Pass them onto active_events to convert them into dicts"""
        if not user.is_authenticated:
            return []
 
        deadlines = Event.objects.filter(
            creator=user,
            #event_type=Event.EventType.DEADLINE,
            is_completed=False,
        ).order_by('start_datetime')
 
        return filter_events(deadlines)
    
    @staticmethod
    def get_filtered_deadlines(user, status_filter='active',sort_order='asc', event_type=None):
        """Get deadlines with status and type filtering and sort order."""
        if not user.is_authenticated:
            return []
        # creates a query set to pass the parameters for filtering
        qs = create_filter_query(user, status_filter, event_type, sort_order)
        return filter_events(qs)
    
    @staticmethod
    def mark_complete(user, event_id):
        """Mark a single event as completed."""
        try:
            event = Event.objects.get(
                pk=event_id,
                creator=user,
                is_completed=False,
            )
            event.is_completed = True
            event.save(update_fields=['is_completed', 'updated_at'])
            return event
        except Event.DoesNotExist:
            return None
        

    @staticmethod
    def mark_incomplete(user, event_id):
        """Mark a single event as incomplete."""
        try:
            event = Event.objects.get(
                pk=event_id,
                creator=user,
                is_completed=True,
            )
            event.is_completed = False
            event.save(update_fields=['is_completed', 'updated_at'])
            return event
        except Event.DoesNotExist:
            return None
        
def create_filter_query(user, status_filter, event_type, sort_order):
    """Build a queryset applying filters.
    Takes parameters from get_filtered_deadlines function and applies them"""
    qs = Event.objects.filter(creator=user)

    if event_type:
        qs = qs.filter(event_type=event_type)

    if status_filter == 'active':
        qs = qs.filter(is_completed=False)
    elif status_filter == 'completed':
        qs = qs.filter(is_completed=True)

    ordering = 'end_datetime' if sort_order == 'asc' else '-end_datetime'
    return qs.order_by(ordering)
    
def filter_events(queryset):
    """Convert a queryset into a list of dicts with urgency and display strings."""
    now = timezone.now()
    return [build_event(event, now) for event in queryset]
    
def build_event(event, now):
    """Build a single dict for one event."""
    time_remaining = event.end_datetime - now
    time_elapsed = now - event.created_at

    return {
        'event': event,
        'urgency_status': urgency_label(event, time_remaining),
        'time_remaining': time_remaining,
        'time_remaining_display': time_string(time_remaining),
        'time_elapsed_display': time_passed(time_elapsed),
    }


def urgency_label(event, time_remaining):
    """Determine the urgency label for an event."""
    if event.is_completed:
        return 'completed'
 
    remaining_seconds = time_remaining.total_seconds()
    if remaining_seconds < 0:
        return 'overdue'
    if remaining_seconds <= 86400:
        return 'urgent'
    return 'normal'

def time_string(td):
    """Human-readable string for time remaining or overdue."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return overdue_time(abs(total_seconds))
    return remaining_time(total_seconds)
 
 
def overdue_time(total_seconds):
    """Format a positive seconds value as 'Xd Yh overdue'."""
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h overdue"
    if hours > 0:
        return f"{hours}h {minutes}m overdue"
    return f"{minutes}m overdue"
 
 
def remaining_time(total_seconds):
    """Format a positive seconds value as 'Xd Yh left'."""
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days > 0:
        return f"{days}d {hours}h left"
    if hours > 0:
        return f"{hours}h {minutes}m left"
    return f"{minutes}m left"
 
 
def time_passed(td):
    """Format elapsed time since creation as 'Added X ago'."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "Added just now"
 
    days = total_seconds // 86400
    if days > 0:
        return f"Added {days} day{'s' if days != 1 else ''} ago"
 
    hours = total_seconds // 3600
    if hours > 0:
        return f"Added {hours} hour{'s' if hours != 1 else ''} ago"
 
    minutes = total_seconds // 60
    if minutes > 0:
        return f"Added {minutes} min ago"
 
    return "Added just now"


