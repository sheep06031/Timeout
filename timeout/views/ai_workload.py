"""
View for generating AI-based workload warnings based on the user's daily events. Accessible only to logged-in users. Caches results for 1 hour to optimize performance and reduce API calls.
"""
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
from timeout.utils import ai_cache_key


def get_ai_workload_warning(user, events):
    """Generate a workload warning message using OpenAI. Cached for 1 hour."""
    if not events or not settings.OPENAI_API_KEY:
        return None

    cache_key = ai_cache_key("workload_warning", user.id)
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        event_summaries = _summarize_events(events)
        warning = _call_openai_workload(event_summaries)
        cache.set(cache_key, warning, timeout=3600)
        return warning
    except Exception:
        return None


def _summarize_events(events):
    """Convert event objects or dicts into summary strings for the AI prompt."""
    summaries = []
    for e in events:
        if isinstance(e, dict):
            title = e.get("title")
            start = e.get("start_datetime")
            end = e.get("end_datetime")
        else:
            title = getattr(e, "title", None)
            start = getattr(e, "start_datetime", None)
            end = getattr(e, "end_datetime", None)
        if not (title and start and end):
            continue
        summaries.append(f"- {title} from {start.strftime('%H:%M')} to {end.strftime('%H:%M')}")
    return summaries


def _call_openai_workload(event_summaries):
    """Call OpenAI to analyze daily workload and return a warning string."""
    from timeout.services.openai_service import call_openai
    system_prompt = (
        "You are a helpful assistant. Analyze the user's daily events and determine "
        "if they are overloaded today or have scheduling conflicts. "
        "Return a concise warning like "
        "'High workload today: 5 events scheduled' or "
        "'Moderate workload, 2 events with minor overlap'."
    )
    user_prompt = "Today's events:\n" + "\n".join(event_summaries)
    return call_openai(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=60,
    )
