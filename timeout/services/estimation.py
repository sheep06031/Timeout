"""
Estimation Service — Learning Loop for task duration predictions.

Place this file at: timeout/services/estimation.py
Then add to timeout/services/__init__.py:
    from .estimation import EstimationService
"""

from django.db.models import Avg
from timeout.models import Event


# Fallback defaults when user has fewer than 3 completed events of a type
DEFAULT_HOURS = {
    'deadline': 2.0,
    'exam': 3.0,
    'class': 1.0,
    'meeting': 1.0,
    'study_session': 2.0,
    'other': 1.0,
}

MIN_SAMPLES = 3  # minimum completed events before we trust the average


class EstimationService:
    """Predicts task duration based on a user's completion history."""

    @staticmethod
    def get_estimated_hours(user, event_type):
        """
        Return the estimated hours for a given event type.

        If the user has completed >= MIN_SAMPLES events of that type,
        return the average of actual_duration_hours.
        Otherwise, return the hardcoded default.
        """
        completed_qs = Event.objects.filter(
            creator=user,
            event_type=event_type,
            is_completed=True,
            actual_duration_hours__isnull=False,
        )

        count = completed_qs.count()

        if count >= MIN_SAMPLES:
            avg = completed_qs.aggregate(
                avg_hours=Avg('actual_duration_hours')
            )['avg_hours']
            return round(avg, 2) if avg else DEFAULT_HOURS.get(event_type, 1.0)

        return DEFAULT_HOURS.get(event_type, 1.0)

    @staticmethod
    def get_all_estimates(user):
        """
        Return a dict of estimated hours for every event type.
        Useful for displaying on the scheduler UI.
        """
        estimates = {}
        for type_code, _ in Event.EventType.choices:
            estimates[type_code] = EstimationService.get_estimated_hours(
                user, type_code
            )
        return estimates

    @staticmethod
    def update_on_complete(event):
        """
        Called when an event is marked complete.
        Updates completed_at and actual_duration_hours.
        """
        event.mark_completed()
        return event