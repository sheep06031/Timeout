"""
Views for moderation actions like flagging posts and banning users. Staff-only actions return JSON for AJAX calls and redirect with messages for regular requests.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from timeout.decorators import staff_required
from timeout.models import Post, User, PostFlag
from timeout.services.notification_service import NotificationService


@login_required
@require_POST
def flag_post(request, post_id):
    """Flag a post for moderation."""
    post = get_object_or_404(Post, id=post_id)
    reason = request.POST.get('reason', 'other')
    description = request.POST.get('description', '').strip()

    if reason not in [c[0] for c in PostFlag.Reason.choices]:
        reason = 'other'

    _, created = PostFlag.objects.get_or_create(
        post=post,
        reporter=request.user,
        defaults={'reason': reason, 'description': description},
    )

    return JsonResponse({'success': True, 'created': created})


@login_required
@staff_required
@require_POST
def approve_flag(request, flag_id):
    """Approve a flag: delete the post and notify its author (staff only)."""
    flag = get_object_or_404(PostFlag, id=flag_id)
    author = flag.post.author
    NotificationService.notify_post_removed(author)
    flag.post.delete()
    return JsonResponse({'success': True})


@login_required
@staff_required
@require_POST
def deny_flag(request, flag_id):
    """Deny a flag: dismiss it and keep the post (staff only)."""
    flag = get_object_or_404(PostFlag, id=flag_id)
    flag.delete()
    return JsonResponse({'success': True})


def _is_ajax(request):
    """Check if request is an AJAX call by examining X-Requested-With header."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
@staff_required
@require_POST
def ban_user(request, username):
    """Ban a user (staff only). Returns JSON for AJAX calls, redirect otherwise."""
    target = get_object_or_404(User, username=username)

    if target.is_staff:
        if _is_ajax(request):
            return JsonResponse({'error': 'Cannot ban a staff member.'}, status=400)
        messages.error(request, 'Cannot ban a staff member.')
        return redirect('user_profile', username=username)

    reason = request.POST.get('reason', '').strip()
    target.is_banned = True
    target.ban_reason = reason
    target.save(update_fields=['is_banned', 'ban_reason'])

    if _is_ajax(request):
        return JsonResponse({'success': True})

    messages.success(request, f'{target.username} has been banned.')
    return redirect('user_profile', username=username)


@login_required
@staff_required
@require_POST
def unban_user(request, username):
    """Unban a user (staff only). Returns JSON for AJAX calls, redirect otherwise."""
    target = get_object_or_404(User, username=username)
    target.is_banned = False
    target.ban_reason = ''
    target.save(update_fields=['is_banned', 'ban_reason'])

    if _is_ajax(request):
        return JsonResponse({'success': True})

    messages.success(request, f'{target.username} has been unbanned.')
    return redirect('user_profile', username=username)
