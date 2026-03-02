from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from timeout.forms import PostForm, CommentForm
from timeout.models import Post, Comment, Like, Bookmark, User, Conversation
from timeout.services import FeedService



@login_required
def feed(request):
    tab = request.GET.get('tab', 'following')

    if tab == 'discover':
        posts = FeedService.get_discover_feed(request.user)
    else:
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

    context = {
        'posts': posts,
        'active_tab': tab,
        'post_form': PostForm(user=request.user),
        'conversation_data': conversation_data,
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

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
    }
    return render(request, 'social/user_profile.html', context)


@login_required
@require_POST
def follow_user(request, username):
    """Follow or unfollow a user (toggle)."""
    user_to_follow = get_object_or_404(User, username=username)

    if user_to_follow == request.user:
        return JsonResponse(
            {'error': 'Cannot follow yourself'}, status=400
        )

    if request.user.following.filter(id=user_to_follow.id).exists():
        # Unfollow
        request.user.following.remove(user_to_follow)
        following = False
        message = f'Unfollowed {user_to_follow.username}'
    else:
        # Follow
        request.user.following.add(user_to_follow)
        following = True
        message = f'Now following {user_to_follow.username}'

    messages.success(request, message)
    return JsonResponse({'following': following})

@login_required
@require_POST
def update_status(request):
    """Update the logged-in user's status via AJAX."""
    status = request.POST.get('status')
    if status not in [s[0] for s in User.Status.choices]:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    request.user.status = status
    request.user.save()
    return JsonResponse({
        'status': status,
        'status_display': request.user.get_status_display()
    })

@login_required
def followers_api(request):
    users = request.user.followers.all()
    return JsonResponse({'users': _serialize_users(users)})

@login_required
def following_api(request):
    users = request.user.following.all()
    return JsonResponse({'users': _serialize_users(users)})

def _serialize_users(users):
    return [
        {
            'username': u.username,
            'full_name': u.get_full_name(),
            'profile_picture': u.profile_picture.url if u.profile_picture else None,
        }
        for u in users
    ]