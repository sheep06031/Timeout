"""
social_service.py - Defines SocialService for managing social interactions: fetching conversation
sidebar data, checking follow/block relationships, and searching users while respecting blocks.
"""


from django.db.models import Q
from timeout.models import (Conversation, Block, FollowRequest, User)
from timeout.services.feed_service import _get_blocked_ids

def _get_conversation_sidebar(user):
    """Get recent conversations for sidebar, with other participant and last message."""
    convs = Conversation.objects.filter(participants=user).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]
    return [{'conv': c, 'other': c.get_other_participant(user), 'last': c.get_last_message()} for c in convs]

def _get_follow_request_info(user, profile_user):
    """Return (has_pending_request, incoming_requests) for the profile."""
    has_pending = FollowRequest.objects.filter(from_user=user, to_user=profile_user).exists()
    incoming = (FollowRequest.objects.filter(to_user=profile_user) if user == profile_user else FollowRequest.objects.none())
    return has_pending, incoming

def are_blocked(user_a, user_b):
    """Return True if any block exists between two users (either direction)."""
    if not user_a or not user_b:
        return False
    return Block.objects.filter(Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)).exists()

def _get_block_status(user, profile_user):
    """Return (is_blocked, has_blocked_me) between two users."""
    is_blocked = Block.objects.filter(blocker=user, blocked=profile_user).exists()
    has_blocked_me = Block.objects.filter(blocker=profile_user, blocked=user).exists()
    return is_blocked, has_blocked_me

def _can_view_profile(user, profile_user, is_blocked, has_blocked_me, is_following):
    """Determine whether user can view profile_user's profile."""
    return (not is_blocked and not has_blocked_me and (user == profile_user or not profile_user.privacy_private or is_following))

def can_view_profile(request_user, profile_user):
    """Convenience wrapper: check if request_user can view profile_user (fetches data)."""
    if request_user == profile_user:
        return True
    if are_blocked(request_user, profile_user):
        return False
    return not profile_user.privacy_private or request_user.following.filter(id=profile_user.id).exists()

def _search_users_queryset(user, query):
    """Return a queryset of users matching query, excluding blocked users."""
    blocked_by_me, blocking_me = _get_blocked_ids(user)
    return User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) |
        Q(last_name__icontains=query)).exclude(id=user.id).exclude(id__in=blocked_by_me).exclude(id__in=blocking_me)[:10]

def _serialize_search_result(u):
    """Serialize a single user for search results."""
    return {'username': u.username, 'full_name': u.get_full_name() or u.username,
        'profile_picture': u.profile_picture.url if u.profile_picture else None, 'status': u.status, 'profile_url': f'/social/user/{u.username}/'}
