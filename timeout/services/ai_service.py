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
    """the service for dashboard summary using OpenAI. 
    Gives out a weekly summary based on user stats"""

    CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours in seconds, timed to update once per day

    @staticmethod
    def get_dashboard_briefing(user):
        """Generate a short AI 'Weekly Insight' summary for the dashboard.
        Results are updated every 24 hours."""
        if not user.is_authenticated: # check authentication
            return None
 
        cache_key = f'ai_briefing_{user.id}' # cache key with user id
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
 
        stats = weekly_stats(user)
        summary = openai_prompt(stats)
        if summary is None:
            return None
 
        cache.set(cache_key, summary, AIService.CACHE_TIMEOUT)
        return summary
 
# Gelper functions to calculate the stats for the briefing
def weekly_stats(user):
    """Gather user stats from the past week"""
    now = timezone.now()
    week_ago = now - timedelta(days=7) # get time from a week ago
    # Event filter from the past week until now
    weekly_events = Event.objects.filter( 
        creator=user,
        start_datetime__gte=week_ago,
        start_datetime__lte=now,
    )
 
    completed_events = weekly_events.filter(is_completed=True) # only get completed events
 # prompt for openai with stats
    return { 
        'total_study_hours': study_hours(weekly_events),
        'missed_deadlines': missed_deadlines(weekly_events, now),
        'most_productive_day': most_productive_day(completed_events),
        'total_events': weekly_events.count(),
        'completed_tasks': completed_events.count(),
    }
 
 
def study_hours(events_qs):
    """Calculate the total hours studied from study session type events"""
    study_events = events_qs.filter(
        event_type=Event.EventType.STUDY_SESSION,
    )
    total_seconds = 0
    for ev in study_events:
        duration = ev.end_datetime - ev.start_datetime
        total_seconds += max(duration.total_seconds(), 0)
    return round(total_seconds / 3600, 1) # Round the results to 1 decimal place after converting to hours
 
 
def missed_deadlines(events_qs, now):
    """Count deadline events that are past due and not completed."""
    return events_qs.filter(
        event_type=Event.EventType.DEADLINE,
        is_completed=False,
        end_datetime__lt=now,
    ).count()
 
 
def most_productive_day(completed_qs):
    """Return the weekday name with the most completed events."""
    day_counts = Counter(
        ev.start_datetime.strftime('%A') for ev in completed_qs # Count the days for completed events and get names of the days
    )
    if day_counts:
        return day_counts.most_common(1)[0][0] # Get the most common day name to find most productive day
    return 'None yet'


# Helper functions to call openai and send prompts

def openai_prompt(stats):
    """Send aggregated stats to OpenAI as prompt
    Returns a 2 sentence briefing."""
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        logger.warning('OPENAI_API_KEY not configured. Skipping AI briefing.')
        return None
 
    prompt = (
        f"Review these student stats for the past week: {json.dumps(stats)}. "
        "Write a 2-sentence 'Morning Briefing' that is encouraging and concise. "
        "Mention one specific win. Do not use markdown formatting."
    )
    return api_call(api_key, prompt)
 
 
def api_call(api_key, prompt):
    """Make the api call to ai with the prompt and return the response"""
    try:
        from openai import OpenAI
 
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini', # model used
            messages=[ # set the tone and the prompt
                {'role': 'system', 'content': 'You are a supportive academic coach. Keep your tone warm, brief, and motivating.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning('OpenAI briefing call failed: %s', exc)
        return None
