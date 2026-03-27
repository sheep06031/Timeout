"""
Tests for social views: user profiles, search, followers/following/friends APIs,
private account access controls.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from timeout.models import FollowRequest

User = get_user_model()


def _make_user(username='testuser', password='TestPass1!', **kwargs):
    return User.objects.create_user(username=username, password=password, **kwargs)


# User Profile: own profile / incoming requests

class UserProfileOwnTests(TestCase):

    def setUp(self):
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_own_profile_shows_incoming_requests(self):
        bob = _make_user('bob')
        FollowRequest.objects.create(from_user=bob, to_user=self.user)
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('incoming_requests', resp.context)
        incoming = list(resp.context['incoming_requests'])
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].from_user, bob)

    def test_own_profile_no_incoming_requests(self):
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(resp.context['incoming_requests'])), 0)

    def test_other_profile_no_incoming_requests(self):
        _make_user('bob')
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['incoming_requests']), [])

    def test_own_profile_has_pending_request_is_false(self):
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertFalse(resp.context['has_pending_request'])


# Search Users

class SearchUsersTests(TestCase):

    def setUp(self):
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_search_empty_query(self):
        resp = self.client.get(reverse('search_users'), {'q': ''})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_no_query_param(self):
        resp = self.client.get(reverse('search_users'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_whitespace_only(self):
        resp = self.client.get(reverse('search_users'), {'q': '   '})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_finds_user_by_username(self):
        _make_user('bob', first_name='Bob', last_name='Smith')
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('bob', usernames)

    def test_search_finds_user_by_first_name(self):
        _make_user('carol', first_name='Carol')
        resp = self.client.get(reverse('search_users'), {'q': 'Carol'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('carol', usernames)

    def test_search_excludes_self(self):
        resp = self.client.get(reverse('search_users'), {'q': 'alice'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('alice', usernames)

    def test_search_no_results(self):
        resp = self.client.get(reverse('search_users'), {'q': 'nonexistentuser123'})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])


# Followers API

class FollowersAPITests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_followers_api_empty(self):
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_followers_api_with_followers(self):
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_followers_api_includes_follow_back_info(self):
        self.bob.following.add(self.alice)
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertTrue(data['users'][0]['is_followed_back'])

    def test_followers_api_not_followed_back(self):
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertFalse(data['users'][0]['is_followed_back'])

    def test_followers_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 302)


# Following API

class FollowingAPITests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_following_api_empty(self):
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_following_api_with_following(self):
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('following_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_following_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 302)


# Friends API

class FriendsAPITests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.charlie = _make_user('charlie')
        self.client.login(username='alice', password='TestPass1!')

    def test_friends_api_empty(self):
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_mutual_follow(self):
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_friends_api_one_way_not_friend(self):
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 302)


# Private Account: user_followers_api / user_following_api

class UserFollowersAPIPrivateTests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_followers_api_private_forbidden(self):
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_following_api_private_forbidden(self):
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_followers_api_private_allowed_if_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_allowed_if_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_own_profile_allowed(self):
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_own_profile_allowed(self):
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_public_always_allowed(self):
        _make_user('public_user', privacy_private=False)
        resp = self.client.get(reverse('user_followers_api', args=['public_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_public_always_allowed(self):
        _make_user('public_user', privacy_private=False)
        resp = self.client.get(reverse('user_following_api', args=['public_user']))
        self.assertEqual(resp.status_code, 200)


# Private Account: user_friends_api

class UserFriendsAPIPrivateTests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_friends_api_private_forbidden(self):
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)

    def test_user_friends_api_private_allowed_if_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_own(self):
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_public(self):
        _make_user('pubuser', privacy_private=False)
        resp = self.client.get(reverse('user_friends_api', args=['pubuser']))
        self.assertEqual(resp.status_code, 200)


# User Profile View: various paths

class UserProfileViewTests(TestCase):

    def setUp(self):
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.private_user = _make_user('private_carol', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_view_public_user_profile(self):
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])

    def test_view_private_user_profile_not_following(self):
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['can_view'])

    def test_view_private_user_profile_following(self):
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])
        self.assertTrue(resp.context['is_following'])

    def test_view_profile_context_keys(self):
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertIn('profile_user', resp.context)
        self.assertIn('posts', resp.context)
        self.assertIn('is_following', resp.context)
        self.assertIn('can_view', resp.context)
        self.assertIn('friends_count', resp.context)
        self.assertIn('has_pending_request', resp.context)
        self.assertIn('incoming_requests', resp.context)

    def test_view_profile_with_pending_request(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertTrue(resp.context['has_pending_request'])

    def test_profile_friends_count(self):
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.context['friends_count'], 1)

    def test_profile_friends_count_private_not_viewable(self):
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.context['friends_count'], 0)