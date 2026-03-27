from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from timeout.forms import PostForm, CommentForm
from timeout.models import Post, Comment, Like, Bookmark, User, Conversation, FocusSession, FollowRequest, PostFlag, Block
from timeout.models.notification import Notification
from timeout.services import FeedService
from timeout.views.profile import get_profile_event


def _get_conversation_sidebar(user):
    convs = Conversation.objects.filter(
        participants=user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]
    return [
        {'conv': c, 'other': c.get_other_participant(user), 'last': c.get_last_message()}
        for c in convs
    ]


def _get_feed_posts(tab, user, cursor=None):
    if tab == 'discover':
        return FeedService.get_discover_feed(user, cursor=cursor)
    elif tab == 'bookmarks':
        return FeedService.get_bookmarked_posts(user, cursor=cursor)
    return FeedService.get_following_feed(user, cursor=cursor)


def _get_feed_content(tab, user):
    """Return (tab, posts, flags) based on the active feed tab."""
    posts, flags = [], []
    if tab == 'review_flags' and user.is_staff:
        flags = PostFlag.objects.select_related(
            'post', 'post__author', 'reporter',
        ).order_by('-created_at')
    else:
        if tab not in ('discover', 'bookmarks'):
            tab = 'following'
        posts = list(_get_feed_posts(tab, user))
    return tab, posts, flags


def _build_feed_context(tab, posts, flags, user, has_more):
    """Build the template context dict for the feed view."""
    return {
        'posts': posts,
        'flags': flags,
        'active_tab': tab,
        'has_more': has_more,
        'next_cursor': posts[-1].id if has_more and posts else None,
        'post_form': PostForm(user=user),
        'conversation_data': _get_conversation_sidebar(user),
        'bookmarked_ids': set(
            Bookmark.objects.filter(user=user).values_list('post_id', flat=True)
        ),
        'liked_ids': set(
            Like.objects.filter(user=user).values_list('post_id', flat=True)
        ),
    }


@login_required
def feed(request):
    """Main social feed view, with tabs for following, discover, and bookmarks."""
    from timeout.services.feed_service import PAGE_SIZE

    tab = request.GET.get('tab', 'following')
    tab, posts, flags = _get_feed_content(tab, request.user)
    has_more = len(posts) > PAGE_SIZE
    posts = posts[:PAGE_SIZE]
    context = _build_feed_context(tab, posts, flags, request.user, has_more)
    return render(request, 'social/feed.html', context)


@login_required
def feed_more(request):
    from timeout.services.feed_service import PAGE_SIZE
    tab = request.GET.get('tab', 'following')
    try:
        cursor = int(request.GET.get('cursor', 0))
    except (ValueError, TypeError):
        cursor = None
    if tab not in ('following', 'discover', 'bookmarks'):
        tab = 'following'
    posts = _get_feed_posts(tab, request.user, cursor=cursor)
    has_more = len(posts) > PAGE_SIZE
    posts = posts[:PAGE_SIZE]
    liked_ids = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))
    bookmarked_ids = set(Bookmark.objects.filter(user=request.user).values_list('post_id', flat=True))
    html = ''.join(render_to_string('social/_post_card.html', {
            'post': post,
            'user': request.user,
            'liked_ids': liked_ids,
            'bookmarked_ids': bookmarked_ids}, request=request) for post in posts)
    return JsonResponse({
        'html': html,
        'has_more': has_more,
        'next_cursor': posts[-1].id if has_more and posts else None})


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

    if Block.objects.filter(
        Q(blocker=request.user, blocked=post.author) |
        Q(blocker=post.author, blocked=request.user)
    ).exists():
        return JsonResponse({'error': 'Cannot interact with this post'}, status=403)

    like, created = Like.objects.get_or_create(user=request.user, post=post)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({'liked': liked, 'like_count': post.get_like_count()})


@login_required
@require_POST
def bookmark_post(request, post_id):
    """Bookmark or unbookmark a post (toggle)."""
    post = get_object_or_404(Post, id=post_id)

    if not post.can_view(request.user):
        return JsonResponse({'error': 'Cannot view post'}, status=403)

    bookmark, created = Bookmark.objects.get_or_create(user=request.user, post=post)

    if not created:
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
    if Block.objects.filter(
        Q(blocker=request.user, blocked=post.author) |
        Q(blocker=post.author, blocked=request.user)).exists():
        return HttpResponseForbidden('Cannot interact with this post')
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
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
@require_POST
def delete_comment(request, comment_id):
    """Delete a comment (author or staff)."""
    comment = get_object_or_404(Comment, id=comment_id)

    if not comment.can_delete(request.user):
        return HttpResponseForbidden('You do not have permission to delete this comment.')

    comment.delete()
    messages.success(request, 'Comment deleted.')
    return redirect('social_feed')


def _get_friends_count(profile_user, can_view):
    """Return the friends count if the profile is viewable, else 0."""
    if can_view:
        return profile_user.following.filter(following=profile_user).count()
    return 0


def _build_user_profile_context(
    request, profile_user, posts, is_following,
    can_view, event, event_status,
    has_pending_request, incoming_requests,
    is_blocked=False, has_blocked_me=False,
):
    """Assemble context dict for a user's profile page."""
    return {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
        'can_view': can_view,
        'event': event,
        'event_status': event_status,
        'friends_count': _get_friends_count(profile_user, can_view),
        'has_pending_request': has_pending_request,
        'incoming_requests': incoming_requests,
        'is_suspended': profile_user.is_banned and not request.user.is_staff,
        'is_blocked': is_blocked,
        'has_blocked_me': has_blocked_me,
    }


def _get_block_status(user, profile_user):
    """Return (is_blocked, has_blocked_me) between two users."""
    is_blocked = Block.objects.filter(blocker=user, blocked=profile_user).exists()
    has_blocked_me = Block.objects.filter(blocker=profile_user, blocked=user).exists()
    return is_blocked, has_blocked_me


def _can_view_profile(user, profile_user, is_blocked, has_blocked_me, is_following):
    """Determine whether user can view profile_user's profile."""
    return (
        not is_blocked and
        not has_blocked_me and
        (user == profile_user or not profile_user.privacy_private or is_following)
    )


def _get_follow_request_info(user, profile_user):
    """Return (has_pending_request, incoming_requests) for the profile."""
    has_pending = FollowRequest.objects.filter(
        from_user=user, to_user=profile_user,
    ).exists()
    incoming = (
        FollowRequest.objects.filter(to_user=profile_user)
        if user == profile_user
        else FollowRequest.objects.none()
    )
    return has_pending, incoming


@login_required
def user_profile(request, username):
    """View a user's profile and their posts."""
    profile_user = get_object_or_404(User, username=username)
    is_blocked, has_blocked_me = _get_block_status(request.user, profile_user)
    posts = FeedService.get_user_posts(profile_user, request.user)
    is_following = request.user.following.filter(
        id=profile_user.id
    ).exists() if request.user.is_authenticated else False
    can_view = _can_view_profile(
        request.user, profile_user, is_blocked, has_blocked_me, is_following,
    )
    event, event_status = get_profile_event(profile_user)
    has_pending_request, incoming_requests = _get_follow_request_info(
        request.user, profile_user,
    )
    context = _build_user_profile_context(
        request, profile_user, posts, is_following, can_view,
        event, event_status, has_pending_request, incoming_requests,
        is_blocked=is_blocked, has_blocked_me=has_blocked_me,
    )
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
    notif_filter.delete()
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

    if Block.objects.filter(
        Q(blocker=request.user, blocked=user_to_follow) |
        Q(blocker=user_to_follow, blocked=request.user)
    ).exists():
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
    if target == request.user:
        return JsonResponse({'error': 'Cannot block yourself'}, status=400)

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
    users = [
        {
            'username': b.blocked.username,
            'full_name': b.blocked.get_full_name(),
            'profile_picture': b.blocked.profile_picture.url if b.blocked.profile_picture else None,
        }
        for b in blocks
    ]
    return JsonResponse({'users': users})

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

def _save_focus_session_if_leaving(user, new_status):
    """Save a FocusSession record if the user is leaving focus mode."""
    if user.status != 'focus' or new_status == 'focus':
        return
    if not user.focus_started_at:
        return
    ended_at = timezone.now()
    duration = int((ended_at - user.focus_started_at).total_seconds())
    if duration > 0:
        FocusSession.objects.create(
            user=user,
            started_at=user.focus_started_at,
            ended_at=ended_at,
            duration_seconds=duration,
        )
    user.focus_started_at = None


@login_required
@require_POST
def update_status(request):
    """Update the logged-in user's status via AJAX."""
    status = request.POST.get('status')
    if status not in [s[0] for s in User.Status.choices]:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    _save_focus_session_if_leaving(request.user, status)

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
    """Get a list of followers for the logged-in user, with an indication of whether they follow back."""
    users = request.user.followers.all()
    following_ids = set(request.user.following.values_list('id', flat=True))
    return JsonResponse({'users': _serialize_users(users, following_ids=following_ids)})


@login_required
def following_api(request):
    """Get a list of users the logged-in user is following."""
    users = request.user.following.all()
    return JsonResponse({'users': _serialize_users(users)})


@login_required
def user_followers_api(request, username):
    """Get a list of followers for a specific user, with privacy checks."""
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
    """Get a list of users a specific user is following, with privacy checks."""
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

def _search_users_queryset(user, query):
    """Return a queryset of users matching query, excluding blocked users."""
    blocked_by_me = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blocking_me = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=user.id).exclude(id__in=blocked_by_me).exclude(id__in=blocking_me)[:10]


def _serialize_search_result(u):
    """Serialize a single user for search results."""
    return {
        'username': u.username,
        'full_name': u.get_full_name() or u.username,
        'profile_picture': u.profile_picture.url if u.profile_picture else None,
        'status': u.status,
        'profile_url': f'/social/user/{u.username}/',
    }


@login_required
def search_users(request):
    """Search users by username or name (GET ?q=...)."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'users': []})
    users = _search_users_queryset(request.user, query)
    results = [_serialize_search_result(u) for u in users]
    return JsonResponse({'users': results})

@login_required
def friends_api(request):
    """Get a list of mutual followers (friends) for the logged-in user."""
    friends = request.user.following.filter(followers=request.user)
    return JsonResponse({'users': _serialize_users(friends)})


@login_required
def user_friends_api(request, username):
    """Get a list of mutual followers (friends) for a specific user, with privacy checks."""
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
    """Helper to serialize user lists with optional following back info."""
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
