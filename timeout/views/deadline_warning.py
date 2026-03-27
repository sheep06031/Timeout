from datetime import timedelta
from django.utils import timezone
from timeout.models import Event


def get_deadline_study_warnings(user):
    """Returns warnings for deadlines in the next 7 days that have no linked study sessions."""

    now = timezone.now()
    next_week = now + timedelta(days=7)

    upcoming_deadlines = Event.objects.filter(
        creator=user,
        event_type=Event.EventType.DEADLINE,
        start_datetime__range=[now, next_week],
        status=Event.EventStatus.UPCOMING)

    warnings = []
    for deadline in upcoming_deadlines:
        if deadline.linked_study_sessions.count() == 0:
            warnings.append({
                'key': f'deadline_warning_{deadline.pk}',
                'message': f"⚠ Deadline '{deadline.title}' has no study sessions scheduled."})

    return warnings