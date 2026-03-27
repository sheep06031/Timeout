from django.test import TestCase
from django.contrib.auth import get_user_model
from timeout.models import Block, FollowRequest, Conversation, Post, Comment
from timeout.services import social_service  

User = get_user_model()

class TestSocialService(TestCase):
    def setUp(self):  # <-- Django expects setUp
        # Set up the users
        self.user = User.objects.create_user(username="user", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        # Set up the conversation
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.user, self.other)

        # Set up the posts
        self.post_public = Post.objects.create(
            author=self.other, content="pub", privacy=Post.Privacy.PUBLIC
        )
        self.post_private = Post.objects.create(
            author=self.other, content="priv", privacy=Post.Privacy.FOLLOWERS_ONLY
        )
        
    def test_get_conversation_sidebar(self):
        sidebar = social_service._get_conversation_sidebar(self.user)
        assert len(sidebar) == 1
        assert sidebar[0]['other'] == self.other

    def test_follow_request_info(self):
        
        # No requests yet
        has_pending, incoming = social_service._get_follow_request_info(self.user, self.other)
        assert not has_pending
        assert incoming.count() == 0

        # Add a pending request
        FollowRequest.objects.create(from_user=self.user, to_user=self.other)
        has_pending, incoming = social_service._get_follow_request_info(self.user, self.other)
        assert has_pending

    def test_block_status(self):
        Block.objects.create(blocker=self.user, blocked=self.other)
        is_blocked, has_blocked_me = social_service._get_block_status(self.user, self.other)
        assert is_blocked
        assert not has_blocked_me

    def test_can_view_profile(self):
        
        # Case: not blocked, not private, not following
        can_view = social_service._can_view_profile(self.user, self.other, False, False, False)
        assert can_view

        # Case: blocked
        can_view = social_service._can_view_profile(self.user, self.other, True, False, True)
        assert not can_view

        # Case: private but following
        self.other.privacy_private = True
        can_view = social_service._can_view_profile(self.user, self.other, False, False, True)
        assert can_view

    def test_search_users_queryset(self):
        
        # Block the other user
        Block.objects.create(blocker=self.user, blocked=self.other)
        qs = social_service._search_users_queryset(self.user, "oth")
        assert self.other not in qs

    def test_serialize_search_result(self):
        result = social_service._serialize_search_result(self.other)
        assert result["username"] == self.other.username
        assert "profile_url" in result