from datetime import datetime
from django.conf import settings
from django.core.cache import cache
from openai import OpenAI


def get_ai_workload_warning(user, events):
    """
    Takes a list of events and generates a workload warning message using OpenAI.
    Cached for 1 hour to avoid repeated API calls.
    """

    if not events or not settings.OPENAI_API_KEY:
        return None

    cache_key = f"ai_workload_warning_{user.id}_{datetime.now().date()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        event_summaries = []
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

            event_summaries.append(
                f"- {title} from {start.strftime('%H:%M')} to {end.strftime('%H:%M')}"
            )

        system_prompt = (
            "You are a helpful assistant. Analyze the user's daily events and determine "
            "if they are overloaded today or have scheduling conflicts. "
            "Return a concise warning like "
            "'High workload today: 5 events scheduled' or "
            "'Moderate workload, 2 events with minor overlap'."
        )

        user_prompt = "Today's events:\n" + "\n".join(event_summaries)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=60,
        )

        warning = response.choices[0].message.content.strip()

        # Cache for 1 hour
        cache.set(cache_key, warning, timeout=3600)

        return warning

    except Exception:
        return None