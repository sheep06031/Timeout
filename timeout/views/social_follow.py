"""
Views for social features: following, blocking, and user search.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from timeout.models import User, FollowRequest, Block, FocusSession
from timeout.models.notification import Notification
from timeout.services.notification_service import NotificationService
from timeout.services.social_service import _serialize_search_result, _search_users_queryset, are_blocked


def _handle_private_follow(from_user, to_user):
    """Toggle a follow request for a private account. Returns True if created."""
    notif_filter = Notification.objects.filter(user=to_user, type=Notification.Type.FOLLOW, message=f"{from_user.username} requested to follow you")
    req, created = FollowRequest.objects.get_or_create(from_user=from_user, to_user=to_user)
    if not created:
        req.delete()
        notif_filter.delete()
        return False
    notif_filter.delete()
    NotificationService.notify_follow_request(to_user, from_user)
    return True

@login_required
@require_POST
def follow_user(request, username):
    """Follow/unfollow a user, or send/cancel a request for private accounts."""
    user_to_follow = get_object_or_404(User, username=username)
    if user_to_follow == request.user: return JsonResponse({'error': 'Cannot follow yourself'}, status=400)
    if are_blocked(request.user, user_to_follow):
        return JsonResponse({'error': 'Cannot follow a blocked user'}, status=403)
    if request.user.following.filter(id=user_to_follow.id).exists():
        request.user.following.remove(user_to_follow)
        return JsonResponse({'following': False, 'requested': False})
    if user_to_follow.privacy_private:
        requested = _handle_private_follow(request.user, user_to_follow)
        return JsonResponse({'following': False, 'requested': requested})
    request.user.following.add(user_to_follow)
    return JsonResponse({'following': True, 'requested': False})

@login_required
@require_POST
def block_user(request, username):
    """Block or unblock a user (toggle)."""
    target = get_object_or_404(User, username=username)
    if target == request.user: return JsonResponse({'error': 'Cannot block yourself'}, status=400)
    block, created = Block.objects.get_or_create(blocker=request.user, blocked=target)
    if created:
        request.user.following.remove(target)
        target.following.remove(request.user)
        FollowRequest.objects.filter(from_user=request.user, to_user=target).delete()
        FollowRequest.objects.filter(from_user=target, to_user=request.user).delete()
        return JsonResponse({'blocked': True})
    block.delete()
    return JsonResponse({'blocked': False})

@login_required
def blocked_users_api(request):
    """Return the list of users blocked by the logged-in user."""
    blocks = Block.objects.filter(blocker=request.user).select_related('blocked')
    users = [{'username': b.blocked.username, 'full_name': b.blocked.get_full_name(),
            'profile_picture': b.blocked.profile_picture.url if b.blocked.profile_picture else None} for b in blocks]
    return JsonResponse({'users': users})

@login_required
@require_POST
def accept_follow_request(request, username):
    """Accept an incoming follow request."""
    from_user = get_object_or_404(User, username=username)
    fr = get_object_or_404(FollowRequest, from_user=from_user, to_user=request.user)
    from_user.following.add(request.user)
    NotificationService.notify_follow_accepted(from_user, request.user)
    fr.delete()
    return JsonResponse({'accepted': True})

@login_required
@require_POST
def reject_follow_request(request, username):
    """Reject an incoming follow request."""
    from_user = get_object_or_404(User, username=username)
    fr = get_object_or_404(FollowRequest, from_user=from_user, to_user=request.user)
    fr.delete()
    return JsonResponse({'rejected': True})

def _save_focus_session_if_leaving(user, new_status):
    """Save a FocusSession record if the user is leaving focus mode."""
    if user.status != 'focus' or new_status == 'focus': return
    if not user.focus_started_at: return
    ended_at = timezone.now()
    duration = int((ended_at - user.focus_started_at).total_seconds())
    if duration > 0: FocusSession.objects.create(user=user, started_at=user.focus_started_at, ended_at=ended_at, duration_seconds=duration)
    user.focus_started_at = None

@login_required
@require_POST
def update_status(request):
    """Update the logged-in user's status via AJAX."""
    status = request.POST.get('status')
    if status not in [s[0] for s in User.Status.choices]: return JsonResponse({'error': 'Invalid status'}, status=400)
    _save_focus_session_if_leaving(request.user, status)
    if status == 'focus': request.user.focus_started_at = timezone.now()
    request.user.status = status
    request.user.save()
    return JsonResponse({'status': status, 'status_display': request.user.get_status_display(),
        'focus_started_at': int(request.user.focus_started_at.timestamp()) if request.user.focus_started_at else None})


@login_required
def search_users(request):
    """Search users by username or name (GET ?q=...)."""
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'users': []})
    users = _search_users_queryset(request.user, query)
    results = [_serialize_search_result(u) for u in users]
    return JsonResponse({'users': results})
