from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models import Block, Post, Conversation
from timeout.services import FeedService

User = get_user_model()


class BlockViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.client.login(username="u1", password="pass123")

    def test_block_user_creates_block(self):
        response = self.client.post(reverse('block_user', args=['u2']))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'blocked': True})
        self.assertTrue(Block.objects.filter(blocker=self.u1, blocked=self.u2).exists())

    def test_unblock_user_removes_block(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('block_user', args=['u2']))
        self.assertJSONEqual(response.content, {'blocked': False})
        self.assertFalse(Block.objects.filter(blocker=self.u1, blocked=self.u2).exists())

    def test_cannot_block_yourself(self):
        response = self.client.post(reverse('block_user', args=['u1']))
        self.assertEqual(response.status_code, 400)

    def test_block_removes_follow_both_directions(self):
        self.u1.following.add(self.u2)
        self.u2.following.add(self.u1)
        self.client.post(reverse('block_user', args=['u2']))
        self.assertFalse(self.u1.following.filter(id=self.u2.id).exists())
        self.assertFalse(self.u2.following.filter(id=self.u1.id).exists())

    def test_blocked_user_cannot_be_followed(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('follow_user', args=['u2']))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.u1.following.filter(id=self.u2.id).exists())

    def test_blocker_cannot_be_followed_by_blocked(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(reverse('follow_user', args=['u2']))
        self.assertEqual(response.status_code, 403)

    def test_blocked_users_api_returns_list(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('blocked_users_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'u2')

    def test_blocked_users_api_empty(self):
        response = self.client.get(reverse('blocked_users_api'))
        data = response.json()
        self.assertEqual(data['users'], [])

    def test_user_profile_blocked_context(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('user_profile', args=['u2']))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_blocked'])
        self.assertFalse(response.context['has_blocked_me'])

    def test_user_profile_blocked_by_context(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('user_profile', args=['u2']))
        self.assertFalse(response.context['is_blocked'])
        self.assertTrue(response.context['has_blocked_me'])

    def test_search_excludes_blocked_user(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('search_users') + '?q=u2')
        data = response.json()
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('u2', usernames)

    def test_search_excludes_user_who_blocked_me(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('search_users') + '?q=u2')
        data = response.json()
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('u2', usernames)


class BlockFeedTest(TestCase):
    def setUp(self):
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
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_discover_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)
        self.assertIn(self.u3.id, author_ids)

    def test_discover_excludes_posts_from_user_who_blocked_me(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        posts = FeedService.get_discover_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)

    def test_following_feed_excludes_blocked_user_posts(self):
        self.u1.following.add(self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_following_feed(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)

    def test_bookmarks_feed_excludes_blocked_user_posts(self):
        from timeout.models import Bookmark
        Bookmark.objects.create(user=self.u1, post=self.post_u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        posts = FeedService.get_bookmarked_posts(self.u1)
        author_ids = [p.author_id for p in posts]
        self.assertNotIn(self.u2.id, author_ids)

class BlockMessagingTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.u1 = User.objects.create_user(username="u1", password="pass123")
        self.u2 = User.objects.create_user(username="u2", password="pass123")
        self.client.login(username="u1", password="pass123")

    def test_blocked_user_cannot_start_conversation(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('start_conversation', args=['u2']))
        self.assertRedirects(response, reverse('inbox'))

    def test_blocking_user_cannot_start_conversation(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.get(reverse('start_conversation', args=['u2']))
        self.assertRedirects(response, reverse('inbox'))

    def test_blocked_user_cannot_send_message(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(
            reverse('send_message', args=[conv.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_send_message(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(
            reverse('send_message', args=[conv.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_view_existing_conversation_when_blocked(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.u1, self.u2)
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.get(reverse('conversation', args=[conv.id]))
        self.assertRedirects(response, reverse('inbox'))

class BlockInteractionTest(TestCase):
    def setUp(self):
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
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_like_post(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 403)

    def test_blocked_user_cannot_comment(self):
        Block.objects.create(blocker=self.u1, blocked=self.u2)
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_blocking_user_cannot_comment(self):
        Block.objects.create(blocker=self.u2, blocked=self.u1)
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertEqual(response.status_code, 403)

    def test_unblocked_user_can_like_post(self):
        response = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['liked'])

    def test_unblocked_user_can_comment(self):
        response = self.client.post(
            reverse('add_comment', args=[self.post.id]),
            {'content': 'hello'},
        )
        self.assertIn(response.status_code, [200, 302])