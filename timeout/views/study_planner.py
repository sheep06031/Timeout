import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.models import Event
from timeout.services.study_planner import get_free_slots, pick_evenly_spaced_slots

logger = logging.getLogger(__name__)


@login_required
@require_POST
def plan_sessions(request):
    """AJAX endpoint to plan study sessions for a given deadline."""
    event_id = request.POST.get('event_id')
    try:
        hours_needed = float(request.POST.get('hours_needed', 4))
        session_length = float(request.POST.get('session_length', 2))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid hours or session length.'}, status=400)

    deadline = get_object_or_404(Event, id=event_id, creator=request.user)
    candidates = _find_candidate_slots(request.user, deadline, hours_needed, session_length)

    if candidates is None:
        return JsonResponse({'success': False, 'error': 'No free time found before this deadline.'}, status=400)

    return _schedule_with_gpt(deadline, hours_needed, session_length, candidates)


def _find_candidate_slots(user, deadline, hours_needed, session_length):
    """Find evenly spaced free slots for the deadline. Returns None if none found."""
    now = timezone.now()
    free_slots = get_free_slots(user, now, deadline.start_datetime, session_length)
    if not free_slots:
        return None
    num_sessions = max(1, int(hours_needed / session_length))
    return pick_evenly_spaced_slots(free_slots, num_sessions, now, deadline.start_datetime)


def _schedule_with_gpt(deadline, hours_needed, session_length, candidates):
    """Call GPT to schedule sessions and return the JSON response."""
    if not getattr(settings, 'OPENAI_API_KEY', ''):
        return JsonResponse({'success': False, 'error': 'OpenAI API key not configured.'}, status=500)
    try:
        sessions = call_gpt(deadline, hours_needed, session_length, candidates)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'AI returned invalid response. Try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)
    if not sessions:
        return JsonResponse({'success': False, 'error': 'AI could not generate sessions. Try again.'}, status=500)
    return JsonResponse({'success': True, 'sessions': sessions})

@login_required
@require_POST
def confirm_sessions(request):
    """AJAX endpoint to confirm and create study sessions after GPT scheduling."""
    try:
        sessions = json.loads(request.POST.get('sessions', '[]'))
        if not isinstance(sessions, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid session data.'}, status=400)

    created = sum(1 for s in sessions if _create_session(request.user, s))
    return JsonResponse({'success': True, 'count': created})


def _create_session(user, s):
    """Create a single study session event. Returns True on success."""
    try:
        start = timezone.make_aware(datetime.fromisoformat(s['start']))
        end = timezone.make_aware(datetime.fromisoformat(s['end']))
        event = Event(
            creator=user, title=s['title'],
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=start, end_datetime=end,
            visibility=Event.Visibility.PRIVATE, allow_conflict=True,
        )
        event.full_clean()
        event.save()
        return True
    except (ValidationError, KeyError, TypeError, ValueError):
        return False


def call_gpt(deadline, hours_needed, session_length, free_slots):
    """Call GPT to schedule sessions based on the deadline and free slots."""
    from openai import OpenAI
    prompt = build_prompt(deadline, hours_needed, session_length, free_slots)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0,
        max_tokens=600,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return json.loads(raw)


def build_prompt(deadline, hours_needed, session_length, candidates):
    """Build a prompt for GPT to schedule study sessions."""
    now = timezone.localtime().strftime('%Y-%m-%d %H:%M %Z')
    due = timezone.localtime(deadline.start_datetime).strftime('%Y-%m-%d %H:%M %Z')
    num_sessions = len(candidates)
    return f"""Today is {now}.
The user needs to prepare for: "{deadline.title}" due {due}.
Each session is exactly {session_length} hours.

I have already chosen {num_sessions} evenly spaced slots for you:
{json.dumps(candidates)}

For each slot, schedule a {session_length}-hour session that starts within the available window.
Return ONLY a valid JSON array of exactly {num_sessions} sessions, no markdown:
[{{"title": "Study for {deadline.title}", "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM"}}]

Rules to follow:
1) Use exactly one session per slot
2) Start time must be within the slot's start-end window
3) End time = start + {session_length} hours
4) Do not schedule in the final 24 hours before the deadline
"""
