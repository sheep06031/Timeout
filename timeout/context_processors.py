from timeout.views.ai_suggestions import get_ai_suggestions
from datetime import date
from timeout.models import Event
from timeout.models.notification import Notification

def ai_suggestions(request):
    if not request.user.is_authenticated:
        return {"ai_suggestions": []}

    # Get today's events for this user
    events_today = Event.objects.filter(
        creator=request.user,
        start_datetime__date=date.today()
    ).order_by('start_datetime')

    suggestions = get_ai_suggestions(request.user, events_today)
    return {"ai_suggestions": suggestions}

def unread_notifications_count(request):
    if request.user.is_authenticated:
        qs = Notification.objects.filter(user=request.user, is_read=False)
        count = qs.count()
        latest = Notification.objects.filter(user=request.user, is_dismissed=False).first()
        latest_notif_id = latest.id if latest else 0
    else:
        count = 0
        latest_notif_id = 0
    return {
        'unread_count': count,
        'latest_notif_id': latest_notif_id,
    }