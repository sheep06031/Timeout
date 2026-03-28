"""
Views for the study planner feature, allowing users to plan study sessions before a deadline using GPT for scheduling.
"""


import json
import logging
from datetime import datetime
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
    candidates, remainder_hours = _find_candidate_slots(request.user, deadline, hours_needed, session_length)

    if candidates is None:
        return JsonResponse({'success': False, 'error': 'No free time found before this deadline.'}, status=400)

    return _schedule_with_gpt(deadline, hours_needed, session_length, candidates, remainder_hours)


def _find_candidate_slots(user, deadline, hours_needed, session_length):
    """Find evenly spaced free slots for the deadline.
    Returns (candidates, remainder_hours) where remainder_hours is the leftover
    study time that doesn't fill a full session (e.g. 1.0 for 10h / 3h sessions).
    Returns (None, 0) if no free time is available."""
    _MIN_REMAINDER = 1 / 60  # ignore remainders shorter than 1 minute
    now = timezone.now()
    num_full = max(1, int(hours_needed / session_length))
    remainder_hours = round(hours_needed - num_full * session_length, 6)
    has_remainder = remainder_hours >= _MIN_REMAINDER
    free_slots = get_free_slots(user, now, deadline.start_datetime, session_length)
    if not free_slots:
        return None, 0
    total_slots = num_full + (1 if has_remainder else 0)
    candidates = pick_evenly_spaced_slots(free_slots, total_slots, now, deadline.start_datetime)
    # Only annotate the extra remainder slot when we actually got it back.
    if has_remainder and len(candidates) == total_slots:
        candidates[-1]['session_hours'] = remainder_hours
    return candidates, remainder_hours if has_remainder else 0


def _schedule_with_gpt(deadline, hours_needed, session_length, candidates, remainder_hours=0.0):
    """Call GPT to schedule sessions and return the JSON response."""
    if not getattr(settings, 'OPENAI_API_KEY', ''):
        return JsonResponse({'success': True, 'sessions': candidates})
    try:
        sessions = call_gpt(deadline, hours_needed, session_length, candidates, remainder_hours)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'AI returned invalid response. Try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)
    if not sessions:
        return JsonResponse({'success': True, 'sessions': candidates})
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
            visibility=Event.Visibility.PRIVATE,
        )
        event.full_clean()
        event.save()
        return True
    except (ValidationError, KeyError, TypeError, ValueError):
        return False


def call_gpt(deadline, hours_needed, session_length, free_slots, remainder_hours=0.0):
    """Call GPT to schedule sessions based on the deadline and free slots."""
    from timeout.services.openai_service import call_openai_json
    prompt = build_prompt(deadline, hours_needed, session_length, free_slots, remainder_hours)
    return call_openai_json([{'role': 'user', 'content': prompt}], max_tokens=600)


def _build_duration_desc(has_remainder, num_full, session_length, remainder_h):
    """Return the session-length description sentence for the GPT prompt."""
    if not has_remainder:
        return f"Each session is exactly {session_length} hours."
    if num_full > 0:
        return (
            f"The first {num_full} session(s) are each {session_length} hours long. "
            f"The last session (the remainder) is {remainder_h} hours long."
        )
    return f"There is 1 session of {remainder_h} hours."


def _build_rules(num_sessions, has_remainder, session_length, remainder_h):
    """Return the numbered rules block for the GPT prompt."""
    full_count = num_sessions - (1 if has_remainder else 0)
    last_rule = (
        f"\n3b) For the LAST slot only: end time = start + {remainder_h} hours"
        if has_remainder else ""
    )
    return (
        f"1) Use exactly one session per slot\n"
        f"2) Start time must be within the slot's start-end window\n"
        f"3) For the first {full_count} slot(s): end time = start + {session_length} hours{last_rule}\n"
        f"4) Do not schedule in the final 24 hours before the deadline"
    )


def build_prompt(deadline, hours_needed, session_length, candidates, remainder_hours=0.0):
    """Build a prompt for GPT to schedule study sessions."""
    _MIN_REMAINDER = 1 / 60
    now = timezone.localtime().strftime('%Y-%m-%d %H:%M %Z')
    due = timezone.localtime(deadline.start_datetime).strftime('%Y-%m-%d %H:%M %Z')
    num_sessions = len(candidates)
    has_remainder = remainder_hours >= _MIN_REMAINDER
    remainder_h = round(remainder_hours, 4)
    num_full = (num_sessions - 1) if has_remainder else num_sessions
    duration_desc = _build_duration_desc(has_remainder, num_full, session_length, remainder_h)
    rules = _build_rules(num_sessions, has_remainder, session_length, remainder_h)
    return (
        f"Today is {now}.\n"
        f"The user needs to prepare for: \"{deadline.title}\" due {due}.\n"
        f"{duration_desc}\n\n"
        f"I have already chosen {num_sessions} evenly spaced slots for you:\n"
        f"{json.dumps(candidates)}\n\n"
        f"For each slot, schedule a session that starts within the available window.\n"
        f"Return ONLY a valid JSON array of exactly {num_sessions} sessions, no markdown:\n"
        f'[{{"title": "Study for {deadline.title}", "start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM"}}]\n\n'
        f"Rules to follow:\n{rules}\n"
    )
