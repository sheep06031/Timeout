"""
Tests for the block and unblock functionality in the timeout app, including the block_user view, the blocked_users_api view, and the context variables set in the user profile and search views related to blocking.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models import Block, Post, Conversation
from timeout.services import FeedService

User = get_user_model()


class BlockViewTest(TestCase):
    """Tests for the block/unblock view and related profile/search context."""

    def setUp(self):
        """Create two users and log in as u1."""
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.client.login(username="u1", password="pass123")

    def test_block_user_creates_block(self):
        """Blocking a user returns JSON with blocked=True and creates a Block record."""
        response = self.client.post(reverse('block_user', args=['u2']))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'blocked': True})
        self.assertTrue(Block.objects.filter(blocker=self.u1, blocked=self.u2).exists())

    def test_unblock_user_removes_block(self):
        """Blocking an already-blocked user toggles it off and returns blocked=False."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('block_user', args=['u2']))
        self.assertJSONEqual(response.content, {'blocked': False})
        self.assertFalse(Block.objects.filter(blocker=self.u1, blocked=self.u2).exists())

    def test_cannot_block_yourself(self):
        """Attempting to block yourself returns 400."""
        response = self.client.post(reverse('block_user', args=['u1']))
        self.assertEqual(response.status_code, 400)

    def test_block_removes_follow_both_directions(self):
        """Blocking a user removes follows in both directions."""
        self.u1.following.add(self.u2)
        self.u2.following.add(self.u1)
        self.client.post(reverse('block_user', args=['u2']))
        self.assertFalse(self.u1.following.filter(id=self.u2.id).exists())
        self.assertFalse(self.u2.following.filter(id=self.u1.id).exists())

    def test_blocked_user_cannot_be_followed(self):
        """Following a user that u1 has blocked returns 403."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('follow_user', args=['u2']))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.u1.following.filter(id=self.u2.id).exists())

    def test_blocker_cannot_be_followed_by_blocked(self):
        """Following a user who has blocked u1 returns 403."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(reverse('follow_user', args=['u2']))
        self.assertEqual(response.status_code, 403)

    def test_blocked_users_api_returns_list(self):
        """The blocked users API returns the list of users blocked by the current user."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('blocked_users_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'u2')

    def test_blocked_users_api_empty(self):
        """The blocked users API returns an empty list when no users are blocked."""
        response = self.client.get(reverse('blocked_users_api'))
        data = response.json()
        self.assertEqual(data['users'], [])

    def test_user_profile_blocked_context(self):
        """Profile context sets is_blocked=True and has_blocked_me=False when u1 blocked u2."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('user_profile', args=['u2']))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_blocked'])
        self.assertFalse(response.context['has_blocked_me'])

    def test_user_profile_blocked_by_context(self):
        """Profile context sets is_blocked=False and has_blocked_me=True when u2 blocked u1."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('user_profile', args=['u2']))
        self.assertFalse(response.context['is_blocked'])
        self.assertTrue(response.context['has_blocked_me'])

    def test_search_excludes_blocked_user(self):
        """User search omits users that the current user has blocked."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('search_users') + '?q=u2')
        data = response.json()
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('u2', usernames)

    def test_search_excludes_user_who_blocked_me(self):
        """User search omits users who have blocked the current user."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('search_users') + '?q=u2')
        data = response.json()
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('u2', usernames)


class BlockFeedTest(TestCase):
    """Tests that block relationships are respected across feed types."""

    def setUp(self):
        """Create three users and a public post for each of u2 and u3."""
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.u3 = User.objects.create_user(username="u3", password="pass123")

        self.post_u2 = Post.objects.create(
            author=self.u2, content="u2 post", privacy=Post.Privacy.PUBLIC
        )
        self.post_u3 = Post.objects.create(
            author=self.u3, content="u3 post", privacy=Post.Privacy.PUBLIC
        )

    def test_discover_excludes_blocked_user_posts(self):
        """Discover feed omits posts from users that u1 has blocked."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_discover_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)
        self.assertIn(self.u3.id, author_ids)

    def test_discover_excludes_posts_from_user_who_blocked_me(self):
        """Discover feed omits posts from users who have blocked u1."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        posts = FeedService.get_discover_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)

    def test_following_feed_excludes_blocked_user_posts(self):
        """Following feed omits posts from a followed user that u1 has since blocked."""
        self.u1.following.add(self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_following_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)

    def test_bookmarks_feed_excludes_blocked_user_posts(self):
        """Bookmarks feed omits posts from users that u1 has blocked."""
        from timeout.models import Bookmark
        Bookmark.objects.create(user=self.u1, post=self.post_u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_bookmarked_posts(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)


class BlockMessagingTest(TestCase):
    """Tests that block relationships prevent messaging between users."""

    def setUp(self):
        """Create two users and log in as u1."""
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.client.login(username="u1", password="pass123")

    def test_blocked_user_cannot_start_conversation(self):
        """u1 cannot start a conversation with a user they have blocked."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('start_conversation', args=['u2']))
        self.assertRedirects(response, reverse('inbox'))

    def test_blocking_user_cannot_start_conversation(self):
        """u1 cannot start a conversation with a user who has blocked them."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('start_conversation', args=['u2']))
        self.assertRedirects(response, reverse('inbox'))

    def test_blocked_user_cannot_send_message(self):
        """u1 cannot send a message in a conversation when they have blocked the other participant."""
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(
            reverse('send_message', args=[conv.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_send_message(self):
        """u1 cannot send a message in a conversation when the other participant has blocked them."""
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(
            reverse('send_message', args=[conv.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_view_existing_conversation_when_blocked(self):
        """u1 is redirected to inbox when viewing a conversation with a blocked user."""
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('conversation', args=[conv.id]))
        self.assertRedirects(response, reverse('inbox'))


class BlockInteractionTest(TestCase):
    """Tests that block relationships prevent liking and commenting on posts."""

    def setUp(self):
        """Create two users, a post by u2, and log in as u1."""
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.post = Post.objects.create(
            author=self.u2,
            content="test post",
            privacy=Post.Privacy.PUBLIC,
        )
        self.client.login(username="u1", password="pass123")

    def test_blocked_user_cannot_like_post(self):
        """u1 cannot like a post authored by a user they have blocked."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_like_post(self):
        """u1 cannot like a post authored by a user who has blocked them."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 403)

    def test_blocked_user_cannot_comment(self):
        """u1 cannot comment on a post authored by a user they have blocked."""
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_comment(self):
        """u1 cannot comment on a post authored by a user who has blocked them."""
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_unblocked_user_can_like_post(self):
        """u1 can like a post when no block exists."""
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['liked'])

    def test_unblocked_user_can_comment(self):
        """u1 can comment on a post when no block exists."""
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertIn(response.status_code, [200, 302])
