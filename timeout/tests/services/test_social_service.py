"""
test_social_service.py - Defines TestSocialService and FeedServiceTest for testing the social_service helper functions and FeedService query logic, including conversation sidebar data,
follow request info, block status, profile visibility, user search functionality, and feed content based on following and discover criteria.
"""


from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from timeout.models import Block, Bookmark, Comment, Conversation, FollowRequest, Like, Post
from timeout.services import FeedService, social_service

User = get_user_model()


class TestSocialService(TestCase):
    """Tests for social_service helper functions."""

    def setUp(self):
        """Set up test data for TestSocialService."""
        self.user = User.objects.create_user(username="user", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.user, self.other)

        self.post_public = Post.objects.create(
            author=self.other, content="pub", privacy=Post.Privacy.PUBLIC
        )
        self.post_private = Post.objects.create(
            author=self.other, content="priv", privacy=Post.Privacy.FOLLOWERS_ONLY
        )

    def test_get_conversation_sidebar(self):
        """Test that _get_conversation_sidebar returns the correct sidebar data."""
        sidebar = social_service._get_conversation_sidebar(self.user)
        assert len(sidebar) == 1
        assert sidebar[0]['other'] == self.other

    def test_follow_request_info(self):
        """Test that _get_follow_request_info returns the correct follow request data."""
        has_pending, incoming = social_service._get_follow_request_info(self.user, self.other)
        assert not has_pending
        assert incoming.count() == 0

        FollowRequest.objects.create(from_user=self.user, to_user=self.other)
        has_pending, incoming = social_service._get_follow_request_info(self.user, self.other)
        assert has_pending

    def test_block_status(self):
        """Test that _get_block_status returns the correct block status."""
        Block.objects.create(blocker=self.user, blocked=self.other)
        is_blocked, has_blocked_me = social_service._get_block_status(self.user, self.other)
        assert is_blocked
        assert not has_blocked_me

    def test_can_view_profile(self):
        """Test that _can_view_profile returns the correct visibility status."""
        can_view = social_service._can_view_profile(self.user, self.other, False, False, False)
        assert can_view

        can_view = social_service._can_view_profile(self.user, self.other, True, False, True)
        assert not can_view

        self.other.privacy_private = True
        can_view = social_service._can_view_profile(self.user, self.other, False, False, True)
        assert can_view

    def test_search_users_queryset(self):
        """Test that _search_users_queryset returns the correct queryset of users."""
        Block.objects.create(blocker=self.user, blocked=self.other)
        qs = social_service._search_users_queryset(self.user, "oth")
        assert self.other not in qs

    def test_serialize_search_result(self):
        """Test that _serialize_search_result returns the correct serialized data."""
        result = social_service._serialize_search_result(self.other)
        assert result["username"] == self.other.username
        assert "profile_url" in result


class FeedServiceTest(TestCase):
    """Tests for FeedService query logic."""

    def setUp(self):
        """Set up test data for FeedServiceTest."""
        self.me = User.objects.create_user(username="me", password="pass123")
        self.a = User.objects.create_user(username="a", password="pass123")
        self.b = User.objects.create_user(username="b", password="pass123")

        self.me.following.add(self.a)

        self.a_pub = Post.objects.create(author=self.a, content="a public", privacy=Post.Privacy.PUBLIC)
        self.a_priv = Post.objects.create(author=self.a, content="a private", privacy=Post.Privacy.FOLLOWERS_ONLY)
        self.b_pub = Post.objects.create(author=self.b, content="b public", privacy=Post.Privacy.PUBLIC)

        Like.objects.create(user=self.me, post=self.b_pub)
        Comment.objects.create(author=self.me, post=self.b_pub, content="wow")
        Bookmark.objects.create(user=self.me, post=self.b_pub)

    def test_following_feed_includes_followed_and_own(self):
        """Test that the following feed includes posts from followed users and the user's own posts."""
        feed = FeedService.get_following_feed(self.me)
        self.assertIn(self.a_pub, feed)
        self.assertIn(self.a_priv, feed)
        self.assertNotIn(self.b_pub, feed)

        my_post = Post.objects.create(author=self.me, content="mine", privacy=Post.Privacy.PUBLIC)
        feed2 = FeedService.get_following_feed(self.me)
        self.assertIn(my_post, feed2)

    def test_discover_feed_excludes_followed_and_own(self):
        """Test that the discover feed excludes posts from followed users and the user's own posts."""
        my_public = Post.objects.create(author=self.me, content="me pub", privacy=Post.Privacy.PUBLIC)
        discover = list(FeedService.get_discover_feed(self.me))
        self.assertNotIn(my_public, discover)
        self.assertNotIn(self.a_pub, discover)
        self.assertIn(self.b_pub, discover)

    def test_discover_feed_only_public(self):
        """Test that the discover feed only includes public posts."""
        Post.objects.create(author=self.b, content="b private", privacy=Post.Privacy.FOLLOWERS_ONLY)
        discover = list(FeedService.get_discover_feed(self.me))
        self.assertTrue(all(p.privacy == Post.Privacy.PUBLIC for p in discover))

    def test_user_posts_privacy_filtered(self):
        """Test that user posts are filtered based on privacy settings."""
        viewer = User.objects.create_user(username="viewer", password="pass123")
        posts = FeedService.get_user_posts(self.a, viewer)
        self.assertIn(self.a_pub, posts)
        self.assertNotIn(self.a_priv, posts)

    def test_bookmarked_posts_privacy_filtered(self):
        """Test that bookmarked posts are filtered based on privacy settings."""
        posts = FeedService.get_bookmarked_posts(self.me)
        self.assertIn(self.b_pub, posts)

        b_private = Post.objects.create(
            author=self.b, content="b private", privacy=Post.Privacy.FOLLOWERS_ONLY,
        )
        Bookmark.objects.create(user=self.me, post=b_private)

        posts_after = FeedService.get_bookmarked_posts(self.me)
        self.assertNotIn(b_private, posts_after)

        self.me.following.add(self.b)
        posts_after_follow = FeedService.get_bookmarked_posts(self.me)
        self.assertIn(b_private, posts_after_follow)

    def test_following_feed_unauth_returns_empty_queryset(self):
        """Test that the following feed returns an empty queryset for anonymous users."""
        anon = AnonymousUser()
        qs = FeedService.get_following_feed(anon)
        self.assertEqual(qs.count(), 0)

    def test_bookmarked_posts_unauth_returns_empty_queryset(self):
        """Test that bookmarked posts return an empty queryset for anonymous users."""
        anon = AnonymousUser()
        qs = FeedService.get_bookmarked_posts(anon)
        self.assertEqual(qs.count(), 0)
