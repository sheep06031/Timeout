from django.db.models import Q
from timeout.models import Post, Block

PAGE_SIZE = 15

def _get_blocked_ids(user):
    """Return (blocked_by_me_ids, blocking_me_ids) for a user."""
    blocked_by_me = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blocking_me = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return blocked_by_me, blocking_me

class FeedService:
    """Service for managing social feed logic."""

    @staticmethod
    def get_following_feed(user, cursor=None):
        if not user.is_authenticated:
            return Post.objects.none()
        
        blocked_by_me, blocking_me = _get_blocked_ids(user)

        following_ids = user.following.values_list('id', flat=True)

        qs = (Post.objects.filter(Q(author_id__in=following_ids) | Q(author=user))
                          .exclude(author__is_banned=True)
                          .exclude(author_id__in=blocked_by_me)
                          .exclude(author_id__in=blocking_me))

        if cursor:
            qs = qs.filter(id__lt=cursor)

        qs = qs.select_related('author', 'event').prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:PAGE_SIZE + 1]

        posts = [p for p in qs if p.can_view(user)]
        return posts

    @staticmethod
    def get_discover_feed(user, cursor=None):
        qs = Post.objects.filter(
            privacy=Post.Privacy.PUBLIC
        ).exclude(author__is_banned=True)

        if user.is_authenticated:
            blocked_by_me, blocking_me = _get_blocked_ids(user)

            following_ids = user.following.values_list('id', flat=True)
            qs = (qs.exclude(author_id__in=following_ids)
                    .exclude(author=user)
                    .exclude(author_id__in=blocked_by_me)
                    .exclude(author_id__in=blocking_me))

        if cursor:
            qs = qs.filter(id__lt=cursor)

        qs = qs.select_related('author', 'event').prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:PAGE_SIZE + 1]

        return list(qs)

    @staticmethod
    def get_user_posts(user, viewer, cursor=None):
        qs = Post.objects.filter(author=user)
        if not (viewer.is_authenticated and viewer.is_staff):
            qs = qs.exclude(author__is_banned=True)

        if cursor:
            qs = qs.filter(id__lt=cursor)

        qs = qs.select_related('author', 'event').prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:PAGE_SIZE + 1]

        return [p for p in qs if p.can_view(viewer)]

    @staticmethod
    def get_bookmarked_posts(user, cursor=None):
        if not user.is_authenticated:
            return Post.objects.none()

        blocked_by_me, blocking_me = _get_blocked_ids(user)

        bookmarked_post_ids = user.bookmarks.values_list('post_id', flat=True)

        qs = (Post.objects.filter(id__in=bookmarked_post_ids)
                          .exclude(author__is_banned=True)
                          .exclude(author_id__in=blocked_by_me)
                          .exclude(author_id__in=blocking_me))

        if cursor:
            qs = qs.filter(id__lt=cursor)

        qs = qs.select_related('author', 'event').prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:PAGE_SIZE + 1]

        return [p for p in qs if p.can_view(user)]
