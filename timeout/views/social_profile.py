"""
Views for social features: user profiles and events on profiles.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from timeout.models import User
from timeout.services import FeedService
from timeout.services.social_service import _get_follow_request_info, _get_block_status, _can_view_profile
from timeout.views.profile import get_profile_event


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
