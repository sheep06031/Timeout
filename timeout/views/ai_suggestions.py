import json
from datetime import datetime
from django.conf import settings
from openai import OpenAI
from django.core.cache import cache


def get_ai_suggestions(user, events_today):
    """
    Generate AI suggestions for today's events.
    `user` is a Django User instance.
    `events_today` is a list of Event model instances.
    Returns a list of strings.
    """

    cache_key = f"ai_suggestions_{user.id}_{datetime.now().date()}"
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
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    prompt = (
        "You are a helpful calendar assistant. The user's events today are:\n" + "\n".join(events_list) +
        "\n\nSuggest 2–3 actionable tips to optimize their day, like when to take breaks, "
        "add focus sessions, or avoid overload. Return a JSON list of strings ONLY.")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a productivity AI assistant."},
            {"role": "user", "content": str(prompt)}],
        temperature=0.7, max_tokens=200)

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]

    suggestions = json.loads(raw)
    if not isinstance(suggestions, list): suggestions = [str(suggestions)]
    return suggestions
