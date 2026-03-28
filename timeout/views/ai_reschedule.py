import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.models import Event



def _query_reschedule_events(user, now, lookahead):
    """Query sessions, deadlines, and fixed events for rescheduling."""
    sessions = Event.objects.filter(
        creator=user,
        event_type=Event.EventType.STUDY_SESSION,
        status=Event.EventStatus.UPCOMING,
        start_datetime__gte=now,
        start_datetime__lte=lookahead,
    ).order_by('start_datetime')
    deadlines = Event.objects.filter(
        creator=user,
        event_type__in=[Event.EventType.DEADLINE, Event.EventType.EXAM],
        start_datetime__gte=now,
        start_datetime__lte=lookahead,
    ).order_by('start_datetime')
    fixed_events = Event.objects.filter(
        creator=user,
        start_datetime__gte=now,
        start_datetime__lte=lookahead,
        status=Event.EventStatus.UPCOMING,
    ).exclude(event_type=Event.EventType.STUDY_SESSION).order_by('start_datetime')
    return sessions, deadlines, fixed_events


def _serialize_events(sessions, deadlines, fixed_events):
    """Serialize event querysets into lists of dicts for the AI prompt."""
    sessions_data = [
        {'id': s.pk, 'title': s.title, 'duration_hours': round((s.end_datetime - s.start_datetime).total_seconds() / 3600, 1)}
        for s in sessions
    ]
    deadlines_data = [
        {'title': d.title, 'due': d.start_datetime.strftime('%Y-%m-%d %H:%M')} for d in deadlines
    ]
    fixed_data = [
        {'title': e.title, 'start': e.start_datetime.strftime('%Y-%m-%d %H:%M'), 'end': e.end_datetime.strftime('%Y-%m-%d %H:%M')}
        for e in fixed_events
    ]
    return sessions_data, deadlines_data, fixed_data


def _build_reschedule_prompt(sessions_data, deadlines_data, fixed_data, now, count):
    """Build the rescheduling prompt string."""
    return f"""Today is {now.strftime('%Y-%m-%d %H:%M')}.

Study sessions to reschedule (keep same duration, assign new times):
{json.dumps(sessions_data)}

Deadlines/exams to study toward (do NOT move these):
{json.dumps(deadlines_data)}

Fixed events to avoid overlapping:
{json.dumps(fixed_data)}

Rules:
- Schedule between 08:00 and 22:00 only
- Spread sessions evenly across the next 3 weeks
- Place sessions before relevant deadlines where possible
- Leave at least 1 hour gap between any two sessions
- Preserve each session's exact duration

Return ONLY a valid JSON array, no markdown:
[{{"id": <id>, "title": "<title>", "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM"}}]
Return all {count} sessions."""


def _get_upcoming_context(user, now):
    """Return serialized upcoming events for the next 7 days."""
    upcoming = Event.objects.filter(
        creator=user,
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(days=7),
        status=Event.EventStatus.UPCOMING,
    ).order_by('start_datetime')
    return [
        {'title': e.title, 'start': e.start_datetime.strftime('%Y-%m-%d %H:%M'), 'end': e.end_datetime.strftime('%Y-%m-%d %H:%M')}
        for e in upcoming
    ]


def _build_suggest_prompt(event, events_context, now, duration_minutes):
    """Build the suggest-reschedule system prompt."""
    return f"""You are a smart study scheduler. Today is {now.strftime('%Y-%m-%d %H:%M')} UTC.

The user missed or cancelled a study session:
- Title: {event.title}
- Duration: {duration_minutes} minutes

Their upcoming events for the next 7 days:
{json.dumps(events_context, ensure_ascii=False)}

Find the best free slot within the next 7 days to reschedule this study session. Prefer daytime hours (08:00-22:00). Avoid placing it during existing events.

Return ONLY valid JSON with no extra text or markdown:
{{
  "start_datetime": "YYYY-MM-DDTHH:MM",
  "end_datetime": "YYYY-MM-DDTHH:MM",
  "reason": "brief explanation of why this slot was chosen"
}}"""


def _suggestion_response(event, data):
    """Build the success JsonResponse for a reschedule suggestion."""
    return JsonResponse({
        'success': True,
        'suggestion': {
            'title': event.title,
            'start_datetime': data.get('start_datetime', ''),
            'end_datetime': data.get('end_datetime', ''),
            'reason': data.get('reason', ''),
            'event_type': 'study_session',
        },
    })


@login_required
@require_POST
def reschedule_study_sessions(request):
    """Ask AI to redistribute all upcoming study sessions into a balanced schedule."""
    now = timezone.now()
    lookahead = now + timedelta(days=21)
    sessions, deadlines, fixed_events = _query_reschedule_events(request.user, now, lookahead)

    if not sessions.exists():
        return JsonResponse({'success': False, 'error': 'No upcoming study sessions found.'}, status=400)

    sessions_data, deadlines_data, fixed_data = _serialize_events(sessions, deadlines, fixed_events)
    prompt = _build_reschedule_prompt(sessions_data, deadlines_data, fixed_data, now, len(sessions_data))

    from timeout.services.openai_service import call_openai_json
    try:
        suggestions = call_openai_json([{'role': 'user', 'content': prompt}], max_tokens=800)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'AI returned an invalid response. Try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)

    original = [
        {'id': s.pk, 'title': s.title, 'start': s.start_datetime.strftime('%Y-%m-%dT%H:%M'), 'end': s.end_datetime.strftime('%Y-%m-%dT%H:%M')}
        for s in sessions
    ]
    return JsonResponse({'success': True, 'suggestions': suggestions, 'original': original})


@login_required
@require_POST
def ai_suggest_reschedule(request):
    """Use OpenAI to suggest a new timeslot for a cancelled/missed study session."""
    event_id = request.POST.get('event_id')
    if not event_id:
        return JsonResponse({'success': False, 'error': 'No event ID provided.'}, status=400)
    if not settings.OPENAI_API_KEY:
        return JsonResponse({'success': False, 'error': 'OpenAI API key not configured.'}, status=500)
    try:
        event = Event.objects.get(pk=event_id, creator=request.user)
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Event not found.'}, status=404)
    now = timezone.now()
    duration_minutes = int((event.end_datetime - event.start_datetime).total_seconds() / 60)
    events_context = _get_upcoming_context(request.user, now)
    system_prompt = _build_suggest_prompt(event, events_context, now, duration_minutes)
    from timeout.services.openai_service import call_openai_json
    try:
        data = call_openai_json(
            [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': 'Suggest the best reschedule slot.'}],
            max_tokens=150,)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'AI returned an invalid response. Please try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)
    return _suggestion_response(event, data)
