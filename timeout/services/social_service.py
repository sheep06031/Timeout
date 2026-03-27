from django.db.models import Q
from django.utils import timezone
from timeout.models import (Conversation, Like, Bookmark, Block, FollowRequest, User, FocusSession)
from timeout.models.notification import Notification

def _get_conversation_sidebar(user):
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

def _search_users_queryset(user, query):
    """Return a queryset of users matching query, excluding blocked users."""
    blocked_by_me = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blocking_me = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) |
        Q(last_name__icontains=query)).exclude(id=user.id).exclude(id__in=blocked_by_me).exclude(id__in=blocking_me)[:10]

def _serialize_search_result(u):
    """Serialize a single user for search results."""
    return {'username': u.username, 'full_name': u.get_full_name() or u.username,
        'profile_picture': u.profile_picture.url if u.profile_picture else None, 'status': u.status, 'profile_url': f'/social/user/{u.username}/'}
