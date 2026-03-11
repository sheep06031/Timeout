import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.models import Event


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

    duration_minutes = int((event.end_datetime - event.start_datetime).total_seconds() / 60)
    now = timezone.now()
    week_end = now + timedelta(days=7)

    # Gather user's upcoming events for the next 7 days as scheduling context
    upcoming = Event.objects.filter(
        creator=request.user,
        start_datetime__gte=now,
        start_datetime__lte=week_end,
        status=Event.EventStatus.UPCOMING,
    ).order_by('start_datetime')

    events_context = [
        {
            'title': e.title,
            'start': e.start_datetime.strftime('%Y-%m-%d %H:%M'),
            'end': e.end_datetime.strftime('%Y-%m-%d %H:%M'),
        }
        for e in upcoming
    ]

    system_prompt = f"""You are a smart study scheduler. Today is {now.strftime('%Y-%m-%d %H:%M')} UTC.

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

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'Suggest the best reschedule slot.'},
            ],
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        data = json.loads(raw)
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': 'AI returned an invalid response. Please try again.'},
            status=500,
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'AI error: {str(e)}'}, status=500)

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
