from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.forms import PostForm, CommentForm
from timeout.models import Post, Comment, Like, Bookmark, User, Conversation, FocusSession, FollowRequest, PostFlag
from timeout.models.notification import Notification
from timeout.services import FeedService
from timeout.views.profile import get_profile_event



@login_required
def feed(request):
    tab = request.GET.get('tab', 'following')

    if tab == 'discover':
        posts = FeedService.get_discover_feed(request.user)
    elif tab == 'bookmarks':
        posts = FeedService.get_bookmarked_posts(request.user)
    else:
        tab = 'following'
        posts = FeedService.get_following_feed(request.user)

    conversations = Conversation.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]

    conversation_data = []
    for conv in conversations:
        conversation_data.append({
            'conv': conv,
            'other': conv.get_other_participant(request.user),
            'last': conv.get_last_message(),
        })
    bookmarked_ids = set(
        Bookmark.objects.filter(user=request.user).values_list('post_id', flat=True)
    )
    liked_ids = set(
        Like.objects.filter(user=request.user).values_list('post_id', flat=True)
    )

    context = {
        'posts': posts,
        'active_tab': tab,
        'post_form': PostForm(user=request.user),
        'conversation_data': conversation_data,
        'bookmarked_ids': bookmarked_ids,
        'liked_ids': liked_ids,
    }
    return render(request, 'social/feed.html', context)

@login_required
def create_post(request):
    """Create a new post."""
    if request.method == 'POST':
        form = PostForm(request.POST, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Post created successfully!')
            return redirect('social_feed')
        else:
            messages.error(request, 'Error creating post.')
    return redirect('social_feed')


@login_required
@require_POST
def delete_post(request, post_id):
    """Delete a post."""
    post = get_object_or_404(Post, id=post_id)

    if not post.can_delete(request.user):
        return HttpResponseForbidden(
            'You do not have permission to delete this post.'
        )

    post.delete()
    messages.success(request, 'Post deleted successfully!')
    return redirect('social_feed')


@login_required
@require_POST
def like_post(request, post_id):
    """Like or unlike a post (toggle)."""
    post = get_object_or_404(Post, id=post_id)

    if not post.can_view(request.user):
        return JsonResponse({'error': 'Cannot view post'}, status=403)

    like, created = Like.objects.get_or_create(
        user=request.user,
        post=post
    )

    if not created:
        # Unlike
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({
        'liked': liked,
        'like_count': post.get_like_count()
    })


@login_required
@require_POST
def bookmark_post(request, post_id):
    """Bookmark or unbookmark a post (toggle)."""
    post = get_object_or_404(Post, id=post_id)

    if not post.can_view(request.user):
        return JsonResponse(
            {'error': 'Cannot view post'}, status=403
        )

    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user,
        post=post
    )

    if not created:
        # Remove bookmark
        bookmark.delete()
        bookmarked = False
    else:
        bookmarked = True

    return JsonResponse({'bookmarked': bookmarked})


@login_required
def bookmarks(request):
    """View bookmarked posts."""
    posts = FeedService.get_bookmarked_posts(request.user)
    context = {'posts': posts}
    return render(request, 'social/bookmarks.html', context)


@login_required
@require_POST
def add_comment(request, post_id):
    """Add a comment to a post."""
    post = get_object_or_404(Post, id=post_id)

    if not post.can_view(request.user):
        return HttpResponseForbidden('Cannot view post')

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post

        # Handle reply to another comment
        parent_id = request.POST.get('parent_id')
        if parent_id:
            parent = get_object_or_404(Comment, id=parent_id)
            comment.parent = parent

        comment.save()
        messages.success(request, 'Comment added!')
    else:
        messages.error(request, 'Error adding comment.')

    return redirect('social_feed')


@login_required
def user_profile(request, username):
    """View a user's profile and their posts."""
    profile_user = get_object_or_404(User, username=username)
    posts = FeedService.get_user_posts(profile_user, request.user)

    is_following = request.user.following.filter(
        id=profile_user.id
    ).exists() if request.user.is_authenticated else False

    can_view = (
        request.user == profile_user or
        not profile_user.privacy_private or
        is_following
    )

    event, event_status = get_profile_event(profile_user) if can_view else (None, None)

    has_pending_request = (
        request.user != profile_user and
        FollowRequest.objects.filter(from_user=request.user, to_user=profile_user).exists()
    )
    incoming_requests = (
        FollowRequest.objects.filter(to_user=request.user).select_related('from_user')
        if request.user == profile_user else []
    )

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
        'can_view': can_view,
        'event': event,
        'event_status': event_status,
        'friends_count': profile_user.following.filter(followers=profile_user).count() if can_view else 0,
        'has_pending_request': has_pending_request,
        'incoming_requests': incoming_requests,
    }
    return render(request, 'social/user_profile.html', context)


def _handle_private_follow(from_user, to_user):
    """Toggle a follow request for a private account. Returns True if created."""
    notif_filter = Notification.objects.filter(
        user=to_user,
        type=Notification.Type.FOLLOW,
        message=f"{from_user.username} requested to follow you",
    )
    req, created = FollowRequest.objects.get_or_create(
        from_user=from_user, to_user=to_user
    )
    if not created:
        req.delete()
        notif_filter.delete()
        return False
    notif_filter.delete()  # clear any leftover before creating a fresh one
    Notification.objects.create(
        user=to_user,
        title="New Follow Request",
        message=f"{from_user.username} requested to follow you",
        type=Notification.Type.FOLLOW,
    )
    return True


@login_required
@require_POST
def follow_user(request, username):
    """Follow/unfollow a user, or send/cancel a request for private accounts."""
    user_to_follow = get_object_or_404(User, username=username)
    if user_to_follow == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

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
def accept_follow_request(request, username):
    """Accept an incoming follow request."""
    from_user = get_object_or_404(User, username=username)
    fr = get_object_or_404(FollowRequest, from_user=from_user, to_user=request.user)
    from_user.following.add(request.user)
    Notification.objects.create(
        user=from_user,
        title="Follow Request Accepted",
        message=f"{request.user.username} accepted your follow request",
        type=Notification.Type.FOLLOW,
    )
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

@login_required
@require_POST
def update_status(request):
    """Update the logged-in user's status via AJAX."""
    status = request.POST.get('status')
    if status not in [s[0] for s in User.Status.choices]:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    # Save focus session when leaving focus mode
    if request.user.status == 'focus' and status != 'focus':
        if request.user.focus_started_at:
            ended_at = timezone.now()
            duration = int((ended_at - request.user.focus_started_at).total_seconds())
            if duration > 0:
                FocusSession.objects.create(
                    user=request.user,
                    started_at=request.user.focus_started_at,
                    ended_at=ended_at,
                    duration_seconds=duration,
                )
            request.user.focus_started_at = None

    # Set focus start time when entering focus mode
    if status == 'focus':
        request.user.focus_started_at = timezone.now()

    request.user.status = status
    request.user.save()

    return JsonResponse({
        'status': status,
        'status_display': request.user.get_status_display(),
        'focus_started_at': int(request.user.focus_started_at.timestamp())
                            if request.user.focus_started_at else None,
    })

@login_required
def followers_api(request):
    users = request.user.followers.all()
    following_ids = set(request.user.following.values_list('id', flat=True))
    return JsonResponse({'users': _serialize_users(users, following_ids=following_ids)})

@login_required
def following_api(request):
    users = request.user.following.all()
    return JsonResponse({'users': _serialize_users(users)})

@login_required
def user_followers_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    can_view = (
        request.user == profile_user or
        not profile_user.privacy_private or
        request.user.following.filter(id=profile_user.id).exists()
    )
    if not can_view:
        return JsonResponse({'error': 'This account is private.'}, status=403)
    users = profile_user.followers.all()
    return JsonResponse({'users': _serialize_users(users)})

@login_required
def user_following_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    can_view = (
        request.user == profile_user or
        not profile_user.privacy_private or
        request.user.following.filter(id=profile_user.id).exists()
    )
    if not can_view:
        return JsonResponse({'error': 'This account is private.'}, status=403)
    users = profile_user.following.all()
    return JsonResponse({'users': _serialize_users(users)})

@login_required
def search_users(request):
    """Search users by username or name (GET ?q=...)."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    results = [
        {
            'username': u.username,
            'full_name': u.get_full_name() or u.username,
            'profile_picture': u.profile_picture.url if u.profile_picture else None,
            'status': u.status,
            'profile_url': f'/social/user/{u.username}/',
        }
        for u in users
    ]
    return JsonResponse({'users': results})

@login_required
def friends_api(request):
    friends = request.user.following.filter(followers=request.user)
    return JsonResponse({'users': _serialize_users(friends)})

@login_required
def user_friends_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    can_view = (
        request.user == profile_user or
        not profile_user.privacy_private or
        request.user.following.filter(id=profile_user.id).exists()
    )
    if not can_view:
        return JsonResponse({'error': 'This account is private.'}, status=403)
    friends = profile_user.following.filter(followers=profile_user)
    return JsonResponse({'users': _serialize_users(friends)})

def _serialize_users(users, following_ids=None):
    result = []
    for u in users:
        entry = {
            'username': u.username,
            'full_name': u.get_full_name(),
            'profile_picture': u.profile_picture.url if u.profile_picture else None,
        }
        if following_ids is not None:
            entry['is_followed_back'] = u.id in following_ids
        result.append(entry)
    return result


# ─── Admin / Moderation Views ───────────────────────────────────────


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

    if created:
        messages.success(request, 'Post has been flagged for review.')
    else:
        messages.info(request, 'You have already flagged this post.')

    return redirect('social_feed')


@login_required
@require_POST
def delete_comment(request, comment_id):
    """Delete a comment (author or staff)."""
    comment = get_object_or_404(Comment, id=comment_id)

    if not comment.can_delete(request.user):
        return HttpResponseForbidden('You do not have permission to delete this comment.')

    comment.delete()
    messages.success(request, 'Comment deleted.')
    return redirect('social_feed')


@login_required
@require_POST
def ban_user(request, username):
    """Ban a user (staff only)."""
    if not request.user.is_staff:
        return HttpResponseForbidden('Staff access required.')

    target = get_object_or_404(User, username=username)

    if target.is_staff:
        messages.error(request, 'Cannot ban a staff member.')
        return redirect('user_profile', username=username)

    reason = request.POST.get('reason', '').strip()
    target.is_banned = True
    target.ban_reason = reason
    target.save(update_fields=['is_banned', 'ban_reason'])

    messages.success(request, f'{target.username} has been banned.')
    return redirect('user_profile', username=username)


@login_required
@require_POST
def unban_user(request, username):
    """Unban a user (staff only)."""
    if not request.user.is_staff:
        return HttpResponseForbidden('Staff access required.')

    target = get_object_or_404(User, username=username)
    target.is_banned = False
    target.ban_reason = ''
    target.save(update_fields=['is_banned', 'ban_reason'])

    messages.success(request, f'{target.username} has been unbanned.')
    return redirect('user_profile', username=username)