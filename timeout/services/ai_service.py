import json
import logging
from collections import Counter
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from timeout.models import Event

logger = logging.getLogger(__name__)


def _get_most_productive_day(events_this_week):
    """Return the weekday name with most completed events, or 'None yet'."""
    completed = events_this_week.filter(is_completed=True)
    day_counts = Counter()
    for ev in completed:
        day_counts[ev.start_datetime.strftime('%A')] += 1
    if day_counts:
        return day_counts.most_common(1)[0][0]
    return 'None yet'


def _gather_study_stats(user, now):
    """Query the last 7 days of events and return aggregated stats dict."""
    week_ago = now - timedelta(days=7)
    events_this_week = Event.objects.filter(
        creator=user,
        start_datetime__gte=week_ago,
        start_datetime__lte=now,
    )

    study_events = events_this_week.filter(event_type=Event.EventType.STUDY_SESSION)
    total_seconds = sum(
        max((ev.end_datetime - ev.start_datetime).total_seconds(), 0)
        for ev in study_events
    )

    missed_deadlines = events_this_week.filter(
        event_type=Event.EventType.DEADLINE,
        is_completed=False,
        end_datetime__lt=now,
    ).count()

    return {
        'total_study_hours': round(total_seconds / 3600, 1),
        'missed_deadlines': missed_deadlines,
        'most_productive_day': _get_most_productive_day(events_this_week),
        'total_events': events_this_week.count(),
        'completed_tasks': events_this_week.filter(is_completed=True).count(),
    }


class AIService:
    """Service for AI-powered dashboard insights using OpenAI. Gives out a weekly briefing based on user stats"""

    CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours in seconds

    @staticmethod
    def get_dashboard_briefing(user):
        """
        Generate a short AI 'Weekly Insight' briefing for the dashboard.
        Results are cached per-user for 24 hours.
        Returns str | None.
        """
        if not user.is_authenticated:
            return None

        cache_key = f'ai_briefing_{user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        stats = _gather_study_stats(user, timezone.now())
        briefing = _call_openai_for_briefing(stats)
        if briefing is None:
            return None

        cache.set(cache_key, briefing, AIService.CACHE_TIMEOUT)
        return briefing


def _format_briefing_prompt(stats):
    """Return the briefing prompt string for the given stats dict."""
    return (
        f"Review these student stats for the past week: {json.dumps(stats)}. "
        "Write a 2-sentence 'Morning Briefing' that is encouraging and concise. "
        "Mention one specific win. Do not use markdown formatting."
    )


def _call_openai_for_briefing(stats):
    """Send aggregated stats to OpenAI and return a 2-sentence briefing. Returns str | None."""
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        logger.warning('OPENAI_API_KEY not configured. Skipping AI briefing.')
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': 'You are a supportive academic coach. Keep your tone warm, brief, and motivating.'},
                {'role': 'user', 'content': _format_briefing_prompt(stats)},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning('OpenAI briefing call failed: %s', exc)
        return None
