from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from timeout.models import User


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


def _can_view_profile(request_user, profile_user):
    return (
        request_user == profile_user or
        not profile_user.privacy_private or
        request_user.following.filter(id=profile_user.id).exists()
    )


@login_required
def followers_api(request):
    users = request.user.followers.all()
    following_ids = set(request.user.following.values_list('id', flat=True))
    return JsonResponse({'users': _serialize_users(users, following_ids=following_ids)})


@login_required
def following_api(request):
    return JsonResponse({'users': _serialize_users(request.user.following.all())})


@login_required
def user_followers_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not _can_view_profile(request.user, profile_user):
        return JsonResponse({'error': 'This account is private.'}, status=403)
    return JsonResponse({'users': _serialize_users(profile_user.followers.all())})


@login_required
def user_following_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not _can_view_profile(request.user, profile_user):
        return JsonResponse({'error': 'This account is private.'}, status=403)
    return JsonResponse({'users': _serialize_users(profile_user.following.all())})


@login_required
def friends_api(request):
    friends = request.user.following.filter(following=request.user)
    return JsonResponse({'users': _serialize_users(friends)})


@login_required
def user_friends_api(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not _can_view_profile(request.user, profile_user):
        return JsonResponse({'error': 'This account is private.'}, status=403)
    friends = profile_user.following.filter(following=profile_user)
    return JsonResponse({'users': _serialize_users(friends)})
