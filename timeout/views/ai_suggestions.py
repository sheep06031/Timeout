"""
View for generating AI-based suggestions to optimize the user's day based on their scheduled events. Accessible only to logged-in users. Caches results for 1 hour to optimize performance and reduce API calls.
"""
import json
from django.conf import settings
from django.core.cache import cache
from timeout.utils import ai_cache_key


def get_ai_suggestions(user, events_today):
    """
    Generate AI suggestions for today's events.
    `user` is a Django User instance.
    `events_today` is a list of Event model instances.
    Returns a list of strings.
    """
    if not getattr(settings, 'OPENAI_API_KEY', ''):
        return []
    cache_key = ai_cache_key("suggestions", user.id)
    cached = cache.get(cache_key)
    if cached:
        return cached
    if not events_today:
        return ["No events today. You have free time!"]
    try:
        events_list = _format_events_for_prompt(events_today)
        suggestions = _call_openai_suggestions(events_list)
        cache.set(cache_key, suggestions, timeout=3600)
        return suggestions
    except json.JSONDecodeError:
        return ["AI returned invalid JSON. Please try again."]
    except Exception as e:
        return [f"AI suggestion unavailable: {str(e)}"]


def _format_events_for_prompt(events_today):
    """Format event objects into human-readable strings for the AI prompt."""
    events_list = []
    for e in events_today:
        if not all(hasattr(e, attr) for attr in ['title', 'start_datetime', 'end_datetime']):
            continue
        events_list.append(
            f"{str(e.title)} from {e.start_datetime.strftime('%H:%M')} to {e.end_datetime.strftime('%H:%M')}"
        )
    return events_list


def _call_openai_suggestions(events_list):
    """Call OpenAI API to generate productivity suggestions for the given events."""
    from timeout.services.openai_service import call_openai_json
    prompt = (
        "You are a helpful calendar assistant. The user's events today are:\n" + "\n".join(events_list) +
        "\n\nSuggest 2–3 actionable tips to optimize their day, like when to take breaks, "
        "add focus sessions, or avoid overload. Return a JSON list of strings ONLY.")
    suggestions = call_openai_json(
        messages=[
            {"role": "system", "content": "You are a productivity AI assistant."},
            {"role": "user", "content": str(prompt)},
        ],
        temperature=0.7,
        max_tokens=200,
    )
    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]
    return suggestions
