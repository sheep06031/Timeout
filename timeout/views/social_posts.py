"""
Views for social features: feed, posts, comments, likes, and bookmarks.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from timeout.forms import PostForm, CommentForm
from timeout.models import Post, Comment, Like, Bookmark, PostFlag
from timeout.services import FeedService
from timeout.services.social_service import _get_conversation_sidebar, are_blocked


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
    """AJAX endpoint to load more posts for infinite scrolling."""
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
