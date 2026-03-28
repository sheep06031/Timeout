"""
Views for social features: feed, posts, comments, likes, bookmarks, profiles, following, blocking.
Endpoints:
- GET /feed: Main feed with tabs for following, discover, and bookmarks
- POST /posts/create: Create a new post
- POST /posts/<id>/delete: Delete a post
- POST /posts/<id>/like: Like/unlike a post (toggle)
- POST /posts/<id>/bookmark: Bookmark/unbookmark a post (toggle)
- POST /posts/<id>/comments/add: Add a comment to a post
- POST /comments/<id>/delete: Delete a comment
- GET /bookmarks: View bookmarked posts
- GET /users/<username>: View a user's profile and posts
- POST /users/<username>/follow: Follow/unfollow a user, or send/cancel a request for private accounts
- POST /users/<username>/block: Block or unblock a user (toggle)
- GET /api/followers: List of current user's followers with follow-back status
- GET /api/following: List of users that current user is following
- GET /api/friends: List of mutual follows (friends) for current user
- GET /api/users/<username>/followers: List of a specific user's followers (respects privacy)
- GET /api/users/<username>/following: List of users that a specific user is following (respects privacy)
- GET /api/users/<username>/friends: List of a specific user's mutual follows (respects privacy)
- POST /update_status: Update the logged-in user's status via AJAX
- POST /reset_focus_timer: Reset focus session timer on page load
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from timeout.services.social_service import (_get_conversation_sidebar,
    _get_follow_request_info, _get_block_status, _can_view_profile,
    _serialize_search_result, _search_users_queryset, are_blocked)
from django.db.models import Q

def _get_user_post_relationships(user):
    """Return liked and bookmarked post ID sets for the given user."""
    return {
        'liked_ids': set(Like.objects.filter(user=user).values_list('post_id', flat=True)),
        'bookmarked_ids': set(Bookmark.objects.filter(user=user).values_list('post_id', flat=True)),
    }


def _toggle_m2m(model, **kwargs):
    """Toggle a relationship: create if absent, delete if present. Returns True if created."""
    obj, created = model.objects.get_or_create(**kwargs)
    if not created:
        obj.delete()
    return created


def _can_interact_with_post(post, user):
    """Return True if user can view and is not blocked from interacting with post."""
    return post.can_view(user) and not are_blocked(user, post.author)


def _get_feed_posts(tab, user, cursor=None):
    """Return feed posts"""
    if tab == 'discover': return FeedService.get_discover_feed(user, cursor=cursor)
    elif tab == 'bookmarks': return FeedService.get_bookmarked_posts(user, cursor=cursor)
    return FeedService.get_following_feed(user, cursor=cursor)

def _get_feed_content(tab, user):
    """Return (tab, posts, flags) based on the active feed tab."""
    posts, flags = [], []
    if tab == 'review_flags' and user.is_staff: flags = PostFlag.objects.select_related('post', 'post__author', 'reporter').order_by('-created_at')
    else:
        if tab not in ('discover', 'bookmarks'): tab = 'following'
        posts = list(_get_feed_posts(tab, user))
    return tab, posts, flags

def _build_feed_context(tab, posts, flags, user, has_more):
    """Build the template context dict for the feed view."""
    return {'posts': posts, 'flags': flags, 'active_tab': tab, 'has_more': has_more, 'next_cursor': posts[-1].id if has_more and posts else None,
        'post_form': PostForm(user=user), 'conversation_data': _get_conversation_sidebar(user),
        **_get_user_post_relationships(user)}

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
    """AJAX endpoint to load more posts for infinite scrolling in the feed."""
    from timeout.services.feed_service import PAGE_SIZE
    tab = request.GET.get('tab', 'following')
    try: cursor = int(request.GET.get('cursor', 0))
    except (ValueError, TypeError): cursor = None
    if tab not in ('following', 'discover', 'bookmarks'): tab = 'following'
    posts = _get_feed_posts(tab, request.user, cursor=cursor)
    has_more = len(posts) > PAGE_SIZE
    posts = posts[:PAGE_SIZE]
    relationships = _get_user_post_relationships(request.user)
    html = ''.join(render_to_string('social/_post_card.html', {'post': post, 'user': request.user,
            **relationships}, request=request) for post in posts)
    return JsonResponse({'html': html, 'has_more': has_more, 'next_cursor': posts[-1].id if has_more and posts else None})

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
        else: messages.error(request, 'Error creating post.')
    return redirect('social_feed')

@login_required
@require_POST
def delete_post(request, post_id):
    """Delete a post."""
    post = get_object_or_404(Post, id=post_id)
    if not post.can_delete(request.user): return HttpResponseForbidden('You do not have permission to delete this post.')
    post.delete()
    messages.success(request, 'Post deleted successfully!')
    return redirect('social_feed')

@login_required
@require_POST
def like_post(request, post_id):
    """Like or unlike a post (toggle)."""
    post = get_object_or_404(Post, id=post_id)
    if not _can_interact_with_post(post, request.user):
        return JsonResponse({'error': 'Cannot interact with this post'}, status=403)
    liked = _toggle_m2m(Like, user=request.user, post=post)
    return JsonResponse({'liked': liked, 'like_count': post.get_like_count()})

@login_required
@require_POST
def bookmark_post(request, post_id):
    """Bookmark or unbookmark a post (toggle)."""
    post = get_object_or_404(Post, id=post_id)
    if not _can_interact_with_post(post, request.user):
        return JsonResponse({'error': 'Cannot interact with this post'}, status=403)
    bookmarked = _toggle_m2m(Bookmark, user=request.user, post=post)
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
    if not _can_interact_with_post(post, request.user):
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
    else: messages.error(request, 'Error adding comment.')
    return redirect('social_feed')

@login_required
@require_POST
def delete_comment(request, comment_id):
    """Delete a comment (author or staff)."""
    comment = get_object_or_404(Comment, id=comment_id)
    if not comment.can_delete(request.user): return HttpResponseForbidden('You do not have permission to delete this comment.')
    comment.delete()
    messages.success(request, 'Comment deleted.')
    return redirect('social_feed')

def _get_friends_count(profile_user, can_view):
    """Return the friends count if the profile is viewable, else 0."""
    if can_view: return profile_user.following.filter(following=profile_user).count()
    return 0

def _build_user_profile_context(
    request, profile_user, posts, is_following,
    can_view, event, event_status,
    has_pending_request, incoming_requests,
    is_blocked=False, has_blocked_me=False):
    """Assemble context dict for a user's profile page."""
    return {'profile_user': profile_user, 'posts': posts, 'is_following': is_following, 'can_view': can_view, 'event': event, 'event_status': event_status,
        'friends_count': _get_friends_count(profile_user, can_view), 'has_pending_request': has_pending_request, 'incoming_requests': incoming_requests,
        'is_suspended': profile_user.is_banned and not request.user.is_staff, 'is_blocked': is_blocked, 'has_blocked_me': has_blocked_me}

@login_required
def user_profile(request, username):
    """View a user's profile and their posts."""
    profile_user = get_object_or_404(User, username=username)
    is_blocked, has_blocked_me = _get_block_status(request.user, profile_user)
    posts = FeedService.get_user_posts(profile_user, request.user)
    is_following = request.user.following.filter(id=profile_user.id).exists() if request.user.is_authenticated else False
    can_view = _can_view_profile(request.user, profile_user, is_blocked, has_blocked_me, is_following)
    event, event_status = get_profile_event(profile_user)
    has_pending_request, incoming_requests = _get_follow_request_info(request.user, profile_user)
    context = _build_user_profile_context(request, profile_user, posts, is_following, can_view,
        event, event_status, has_pending_request, incoming_requests, is_blocked=is_blocked, has_blocked_me=has_blocked_me)
    return render(request, 'social/user_profile.html', context)

def _handle_private_follow(from_user, to_user):
    notif_filter = Notification.objects.filter(
        user=to_user,
        type=Notification.Type.FOLLOW,
        message=f"{from_user.username} requested to follow you"
    )
    req, created = FollowRequest.objects.get_or_create(from_user=from_user, to_user=to_user)
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
        sender=from_user 
    )
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
    Notification.objects.create(user=from_user, title="Follow Request Accepted",
        message=f"{request.user.username} accepted your follow request", type=Notification.Type.FOLLOW)
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
@require_POST
def reset_focus_timer(request):
    """Reset focus session timer on page load. Creates a new session with timer at 0."""
    user = request.user
    if user.status == 'focus':
        user.focus_started_at = timezone.now()
        user.save()
    return JsonResponse({'success': True})


@login_required
def search_users(request):
    """Search users by username or name (GET ?q=...)."""
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'users': []})
    users = _search_users_queryset(request.user, query)
    results = [_serialize_search_result(u) for u in users]
    return JsonResponse({'users': results})


