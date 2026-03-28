"""
Service layer for Event-related business logic. This is where complex queries and data transformations related to Events should live, keeping views thin and focused on HTTP handling.
"""

from django.utils import timezone
from timeout.models import Event


class EventService:
    """Service for building and querying Event objects."""

    @staticmethod
    def get_dashboard_upcoming(user, limit=5):
        """Return upcoming/ongoing events for the dashboard schedule widget."""
        now = timezone.now()
        return Event.objects.filter(
            creator=user,
            start_datetime__gte=now,
            status__in=['upcoming', 'ongoing'],
        ).order_by('start_datetime')[:limit]

    @staticmethod
    def build_from_data(user, data):
        """Instantiate (but do not save) an Event from a normalised data dict.

        Expected keys:
            title, event_type, start_datetime, end_datetime,
            location, description, allow_conflict, visibility,
            is_all_day, recurrence
        """
        return Event(
            creator=user,
            title=data['title'],
            event_type=data.get('event_type', 'other'),
            start_datetime=data['start_datetime'],
            end_datetime=data['end_datetime'],
            location=data.get('location', ''),
            description=data.get('description', ''),
            allow_conflict=data.get('allow_conflict', False),
            visibility=data.get('visibility', 'private'),
            is_all_day=data.get('is_all_day', False),
            recurrence=data.get('recurrence', 'none'),
        )
