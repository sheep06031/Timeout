"""
Views for user notifications, including listing, marking as read/unread, and deleting notifications.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from timeout.models.notification import Notification
from django.http import JsonResponse
from django.core.paginator import Paginator
from timeout.services.notification_service import NotificationService


@login_required
def notifications_view(request):
    """Display user notifications with pagination and filtering."""
    notifications_qs = Notification.objects.filter(user=request.user, is_dismissed=False).order_by('-created_at')
    unread_count = notifications_qs.filter(is_read=False).count()
    filter_param = request.GET.get('filter')
    if filter_param == 'unread': notifications_qs = notifications_qs.filter(is_read=False)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return _notifications_ajax(notifications_qs, request.GET.get('page', 1))
    return render(request, 'pages/notifications.html', {
        'notifications': notifications_qs,
        'unread_count': unread_count,
        'current_filter': filter_param})


def _notifications_ajax(queryset, page_number):
    """Return paginated notifications as JSON."""
    paginator = Paginator(queryset, 15)
    page_obj = paginator.get_page(page_number)
    data = [_serialize_notification(n) for n in page_obj]
    return JsonResponse({
        'notifications': data,
        'has_next': page_obj.has_next(),
        'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
    })


def _serialize_notification(n):
    """Convert a Notification instance to a JSON-safe dict."""
    return {
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'deadline_id': n.deadline_id,
        'conversation_id': n.conversation_id,
        'post_id': n.post_id,
    }

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read."""
    try: 
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def mark_all_notifications_unread(request):
    """Mark all notifications as unread (for testing or user preference)."""
    Notification.objects.filter(
        user=request.user, is_read=True, is_dismissed=False
    ).update(is_read=False)
    return JsonResponse({'success': True})

@login_required
def delete_notification(request, notification_id):
    """Dismiss a notification (mark as dismissed and read)."""
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_dismissed = True
        n.is_read = True
        n.save(update_fields=['is_dismissed', 'is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False, is_dismissed=False).update(is_read=True)
    return JsonResponse({'success': True})

@login_required
def mark_notification_unread(request, notification_id):
    """Mark a specific notification as unread."""
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = False
        n.save(update_fields=['is_read'])
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)

@login_required
def delete_all_notifications(request):
    """Delete all notifications for the current user."""
    Notification.objects.filter(
        user=request.user, is_dismissed=False
    ).update(is_dismissed=True, is_read=True)
    return JsonResponse({'success': True})

@login_required
def poll_notifications(request):
    """AJAX endpoint to poll for new notifications since last_id."""
    try:
        last_id = int(request.GET.get('last_id', 0))
    except (ValueError, TypeError):
        last_id = 0
    NotificationService.create_deadline_notifications(request.user)
    NotificationService.create_event_notifications(request.user)
    notifications = Notification.objects.filter(
        user=request.user,
        id__gt=last_id,
        is_dismissed=False).order_by('id')
    data = [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.strftime('%H:%M'),
            'is_read': bool(n.is_read)}
        for n in notifications]
    unread_count = Notification.objects.filter(
        user=request.user, is_read=False, is_dismissed=False).count()
    return JsonResponse({'notifications': data, 'unread_count': unread_count})