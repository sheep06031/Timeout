from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from timeout.models.notification import Notification
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST


@login_required
def notifications_view(request):

    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')

    unread_count = notifications_qs.filter(is_read=False).count()

    paginator = Paginator(notifications_qs, 10)  # 10 notifications per page
    page_number = request.GET.get('page')
    notifications = paginator.get_page(page_number)

    return render(request, 'pages/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })

@login_required
@require_POST
def delete_notification(request, notification_id):
    try:
        notif = Notification.objects.get(id=notification_id, user=request.user)
        notif.delete()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
@require_POST
def clear_read_notifications(request):
    request.user.notifications.filter(is_read=True).delete()
    return JsonResponse({'success': True})

@login_required
def mark_notification_read(request, notification_id):
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def poll_notifications(request):
    try:
        last_id = int(request.GET.get('last_id', 0))
    except (ValueError, TypeError):
        last_id = 0

    from timeout.services.notification_service import NotificationService
    NotificationService.create_deadline_notifications(request.user)

    notifications = Notification.objects.filter(user=request.user, id__gt=last_id).order_by('id')

    data = [
        {
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.strftime('%H:%M'),
            'is_read': bool(n.is_read),
        }
        for n in notifications
    ]

    return JsonResponse({'notifications': data})