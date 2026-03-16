import json
import logging
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum, F
from django.utils import timezone

from timeout.models import Event

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered dashboard insights using OpenAI."""

    CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours in seconds

    @staticmethod
    def get_dashboard_briefing(user):
        """
        Generate a short AI 'Weekly Insight' briefing for the dashboard.

        Queries the user's Event data from the past 7 days, aggregates key
        stats (study hours, missed deadlines, most productive day), then
        asks OpenAI for a concise 2-sentence morning briefing.

        Results are cached per-user for 24 hours.

        Returns:
            str | None: The briefing text, or None on any failure.
        """
        if not user.is_authenticated:
            return None

        cache_key = f'ai_briefing_{user.id}'

        # Try cache first
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # ── Gather stats from the last 7 days ──────────────────────────
        now = timezone.now()
        week_ago = now - timedelta(days=7)

        events_this_week = Event.objects.filter(
            creator=user,
            start_datetime__gte=week_ago,
            start_datetime__lte=now,
        )

        # Total study hours (study_session events)
        study_events = events_this_week.filter(
            event_type=Event.EventType.STUDY_SESSION,
        )
        total_study_seconds = 0
        for ev in study_events:
            duration = (ev.end_datetime - ev.start_datetime).total_seconds()
            if duration > 0:
                total_study_seconds += duration
        total_study_hours = round(total_study_seconds / 3600, 1)

        # Missed deadlines (deadline type, not completed, end_datetime in the past)
        missed_deadlines = events_this_week.filter(
            event_type=Event.EventType.DEADLINE,
            is_completed=False,
            end_datetime__lt=now,
        ).count()

        # Most productive day (day with most is_completed=True events)
        completed_events = events_this_week.filter(is_completed=True)
        day_counts = Counter()
        for ev in completed_events:
            day_label = ev.start_datetime.strftime('%A')  # e.g. "Monday"
            day_counts[day_label] += 1

        if day_counts:
            most_productive_day = day_counts.most_common(1)[0][0]
        else:
            most_productive_day = 'None yet'

        # Total events this week for extra context
        total_events = events_this_week.count()

        stats = {
            'total_study_hours': total_study_hours,
            'missed_deadlines': missed_deadlines,
            'most_productive_day': most_productive_day,
            'total_events': total_events,
            'completed_tasks': completed_events.count(),
        }

        # ── Call OpenAI ─────────────────────────────────────────────────
        briefing = _call_openai_for_briefing(stats)
        if briefing is None:
            return None

        # Cache for 24 hours
        cache.set(cache_key, briefing, AIService.CACHE_TIMEOUT)
        return briefing


def _call_openai_for_briefing(stats):
    """
    Send aggregated stats to OpenAI and return a 2-sentence briefing.

    Returns:
        str | None: The briefing text, or None on failure.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        logger.warning('OPENAI_API_KEY not configured. Skipping AI briefing.')
        return None

    prompt = (
        f"Review these student stats for the past week: {json.dumps(stats)}. "
        "Write a 2-sentence 'Morning Briefing' that is encouraging and concise. "
        "Mention one specific win. Do not use markdown formatting."
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a supportive academic coach. '
                        'Keep your tone warm, brief, and motivating.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.exception('OpenAI briefing call failed: %s', exc)
        return None