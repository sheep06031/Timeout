import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.models import Event


def _strip_code_fence(raw):
    """Remove markdown code fences from a string."""
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return raw


def _call_openai_parse_event(user_input, system_prompt):
    """Call OpenAI to parse natural language into event JSON. Returns dict or raises."""
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_input},
        ],
        temperature=0,
        max_tokens=300,
    )
    raw = _strip_code_fence(response.choices[0].message.content.strip())
    return json.loads(raw)


def _build_event_from_data(user, data):
    """Construct an Event instance from AI-parsed data dict."""
    is_all_day = bool(data.get('is_all_day', False))
    start_str = data.get('start_datetime', '')
    end_str = data.get('end_datetime', '')

    if is_all_day and start_str:
        date_part = start_str.split('T')[0]
        start_str = f"{date_part}T00:00"
        end_str = f"{date_part}T23:59"

    return Event(
        creator=user,
        title=data.get('title', 'Untitled'),
        event_type=data.get('event_type', 'other'),
        start_datetime=start_str,
        end_datetime=end_str,
        location=data.get('location', ''),
        description=data.get('description', ''),
        recurrence=data.get('recurrence', 'none'),
        is_all_day=is_all_day,
        visibility=data.get('visibility', 'private'),
        allow_conflict=False,
    )


def _get_events_context(user, now):
    """Return upcoming event dicts for use as conflict context in the prompt."""
    existing = Event.objects.filter(
        creator=user,
        end_datetime__gte=now,
    ).order_by('start_datetime')[:20]
    return [
        {
            'title': e.title,
            'start': e.start_datetime.strftime('%Y-%m-%d %H:%M'),
            'end': e.end_datetime.strftime('%Y-%m-%d %H:%M'),
        }
        for e in existing
    ]


def _build_system_prompt(user, now):
    """Build the system prompt with existing events as conflict context."""
    events_context = _get_events_context(user, now)
    return f"""You are a calendar assistant. Today is {now.strftime('%Y-%m-%d %H:%M')} UTC.

User's existing upcoming events:
{json.dumps(events_context, ensure_ascii=False)}

Parse the user's message and return ONLY valid JSON with no extra text or markdown:
{{
  "title": "string (required)",
  "event_type": "deadline|exam|class|meeting|study_session|other",
  "start_datetime": "YYYY-MM-DDTHH:MM",
  "end_datetime": "YYYY-MM-DDTHH:MM",
  "location": "",
  "description": "",
  "recurrence": "none|daily|weekly|monthly",
  "is_all_day": false,
  "visibility": "private"
}}

Interpret relative dates like "tomorrow", "next Monday" based on today's date.
Default duration is 1 hour if not specified."""


def _save_and_respond(event):
    """Validate and save the event, returning a JsonResponse."""
    try:
        event.full_clean()
        event.save()
        return JsonResponse({
            'success': True,
            'event': {
                'title': event.title,
                'start': event.start_datetime.strftime('%Y-%m-%d %H:%M'),
                'end': event.end_datetime.strftime('%Y-%m-%d %H:%M'),
                'event_type': event.event_type,
            },
        })
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def ai_create_event(request):
    """Parse natural language input with OpenAI and create a calendar Event."""
    user_input = request.POST.get('user_input', '').strip()
    if not user_input:
        return JsonResponse({'success': False, 'error': 'No input provided.'}, status=400)

    if not settings.OPENAI_API_KEY:
        return JsonResponse({'success': False, 'error': 'OpenAI API key not configured.'}, status=500)

    system_prompt = _build_system_prompt(request.user, timezone.now())

    try:
        data = _call_openai_parse_event(user_input, system_prompt)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'AI returned an invalid response. Please try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)

    return _save_and_respond(_build_event_from_data(request.user, data))
