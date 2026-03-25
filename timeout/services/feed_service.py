from django.db.models import Q, Count
from timeout.models import Post

class FeedService:
    """Service for managing social feed logic."""

    @staticmethod
    def get_following_feed(user, limit=50):
        """
        Get posts from users that the current user follows.
        Ordered by creation time (newest first).
        """
        if not user.is_authenticated:
            return Post.objects.none()

        # Get posts from followed users
        following_ids = user.following.values_list('id', flat=True)

        # Include user's own posts in following feed
        feed = Post.objects.filter(
            Q(author_id__in=following_ids) | Q(author=user)
        ).exclude(author__is_banned=True).select_related(
            'author', 'event'
        ).prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:limit]

        # Filter by privacy
        viewable_posts = [
            post for post in feed if post.can_view(user)
        ]

        return viewable_posts

    @staticmethod
    def get_discover_feed(user, limit=50):
        """
        Get public posts from all users, ordered by engagement.
        Shows popular posts the user hasn't seen from
        people they don't follow.
        """
        # Base query: all public posts
        feed = Post.objects.filter(
            privacy=Post.Privacy.PUBLIC
        ).exclude(author__is_banned=True)

        # Exclude posts from users already being followed
        if user.is_authenticated:
            following_ids = user.following.values_list('id', flat=True)
            feed = feed.exclude(author_id__in=following_ids)
            # Exclude own posts
            feed = feed.exclude(author=user)

        # Annotate with engagement metrics
        feed = feed.annotate(
            like_count=Count('likes', distinct=True),
            comment_count=Count('comments', distinct=True)
        ).select_related(
            'author', 'event'
        ).prefetch_related(
            'likes', 'comments', 'bookmarks'
        )

        # Order by engagement (likes + comments) and recency
        feed = feed.order_by(
            '-like_count', '-comment_count', '-created_at'
        )[:limit]

        return feed

    @staticmethod
    def get_user_posts(user, viewer, limit=50):
        """
        Get posts from a specific user, filtered by privacy.
        viewer is the user requesting to see the posts.
        """
        posts = Post.objects.filter(author=user)
        if not (viewer.is_authenticated and viewer.is_staff):
            posts = posts.exclude(author__is_banned=True)
        posts = posts.select_related(
            'author', 'event'
        ).prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:limit]

        # Filter by privacy
        viewable_posts = [
            post for post in posts if post.can_view(viewer)
        ]

        return viewable_posts

    @staticmethod
    def get_bookmarked_posts(user, limit=50):
        """Get posts bookmarked by the user."""
        if not user.is_authenticated:
            return Post.objects.none()

        bookmarked_post_ids = user.bookmarks.values_list(
            'post_id', flat=True
        )

        posts = Post.objects.filter(
            id__in=bookmarked_post_ids
        ).exclude(author__is_banned=True).select_related(
            'author', 'event'
        ).prefetch_related(
            'likes', 'comments', 'bookmarks'
        ).order_by('-created_at')[:limit]

        
        viewable_posts = [
            post for post in posts if post.can_view(user)
        ]

        return viewable_posts
