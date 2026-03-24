from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from timeout.models.notification import Notification
from timeout.models.follow_request import FollowRequest
from django.http import JsonResponse
from django.core.paginator import Paginator
from timeout.services.notification_service import NotificationService


@login_required
def notifications_view(request):
    notifications_qs = Notification.objects.filter(
        user=request.user,
        is_dismissed=False
    ).order_by('-created_at')

    unread_count = notifications_qs.filter(is_read=False).count()

    # Filter by unread if requested
    filter_param = request.GET.get('filter')
    if filter_param == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)

    paginator = Paginator(notifications_qs, 10)
    page_number = request.GET.get('page')
    notifications = paginator.get_page(page_number)

    pending_usernames = set(
        FollowRequest.objects.filter(to_user=request.user)
        .values_list('from_user__username', flat=True)
    )
    for n in notifications:
        n.follow_request_username = None
        if n.type == Notification.Type.FOLLOW and 'requested to follow you' in n.message:
            username = n.message.split(' requested to follow you')[0]
            if username in pending_usernames:
                n.follow_request_username = username

    return render(request, 'pages/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
        'current_filter': filter_param,
    })


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
def delete_notification(request, notification_id):
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_dismissed = True
        n.is_read = True
        n.save(update_fields=['is_dismissed', 'is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def poll_notifications(request):
    try:
        last_id = int(request.GET.get('last_id', 0))
    except (ValueError, TypeError):
        last_id = 0

    NotificationService.create_deadline_notifications(request.user)
    NotificationService.create_event_notifications(request.user)  # ADD THIS

    notifications = Notification.objects.filter(
        user=request.user,
        id__gt=last_id,
        is_dismissed=False
    ).order_by('id')

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

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
        is_dismissed=False
    ).count()

    return JsonResponse({'notifications': data, 'unread_count': unread_count})