from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from timeout.models import Post, User, PostFlag
from timeout.models.notification import Notification


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
@require_POST
def approve_flag(request, flag_id):
    """Approve a flag: delete the post and notify its author (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff access required.'}, status=403)

    flag = get_object_or_404(PostFlag, id=flag_id)
    author = flag.post.author
    Notification.objects.create(
        user=author,
        title='⚠️ Post Removed',
        message='Your post was removed by a moderator.',
        type=Notification.Type.EVENT,
    )
    flag.post.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def deny_flag(request, flag_id):
    """Deny a flag: dismiss it and keep the post (staff only)."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff access required.'}, status=403)

    flag = get_object_or_404(PostFlag, id=flag_id)
    flag.delete()
    return JsonResponse({'success': True})


def _is_ajax(request):
    """Check if request is an AJAX call by examining X-Requested-With header."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
@require_POST
def ban_user(request, username):
    """Ban a user (staff only). Returns JSON for AJAX calls, redirect otherwise."""
    if not request.user.is_staff:
        if _is_ajax(request):
            return JsonResponse({'error': 'Staff access required.'}, status=403)
        return HttpResponseForbidden('Staff access required.')

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
@require_POST
def unban_user(request, username):
    """Unban a user (staff only). Returns JSON for AJAX calls, redirect otherwise."""
    if not request.user.is_staff:
        if _is_ajax(request):
            return JsonResponse({'error': 'Staff access required.'}, status=403)
        return HttpResponseForbidden('Staff access required.')

    target = get_object_or_404(User, username=username)
    target.is_banned = False
    target.ban_reason = ''
    target.save(update_fields=['is_banned', 'ban_reason'])

    if _is_ajax(request):
        return JsonResponse({'success': True})

    messages.success(request, f'{target.username} has been unbanned.')
    return redirect('user_profile', username=username)
