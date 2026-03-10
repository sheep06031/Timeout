from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from timeout.models.notification import Notification
from django.http import JsonResponse

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'pages/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_read(request, notification_id):
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)