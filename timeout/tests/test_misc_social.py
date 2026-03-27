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
    """Helper function to create a user with the given username and password, along with any additional fields."""
    return User.objects.create_user(username=username, password=password, **kwargs)


# User Profile: own profile / incoming requests

class UserProfileOwnTests(TestCase):
    """Tests for viewing own user profile, covering the presence of incoming follow requests, pending request status, and the friends count in the profile context for both public and private accounts."""

    def setUp(self):
        """Set up a test user and log them in before each test."""
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_own_profile_shows_incoming_requests(self):
        """Test that the user profile view for the logged-in user includes incoming follow requests in the context when there are pending requests."""
        bob = _make_user('bob')
        FollowRequest.objects.create(from_user=bob, to_user=self.user)
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('incoming_requests', resp.context)
        incoming = list(resp.context['incoming_requests'])
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].from_user, bob)

    def test_own_profile_no_incoming_requests(self):
        """Test that the user profile view for the logged-in user shows an empty list of incoming follow requests when there are no pending requests."""
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(resp.context['incoming_requests'])), 0)

    def test_other_profile_no_incoming_requests(self):
        """Test that viewing another user's profile does not include incoming follow requests in the context."""
        _make_user('bob')
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['incoming_requests']), [])

    def test_own_profile_has_pending_request_is_false(self):
        """Test that the has_pending_request context variable is False when there are no pending follow requests for the logged-in user's own profile."""
        resp = self.client.get(reverse('user_profile', args=['alice']))
        self.assertFalse(resp.context['has_pending_request'])

class SearchUsersTests(TestCase):
    """Tests for the search_users view, covering various scenarios of search queries including empty, whitespace-only, valid username/first name, and ensuring the logged-in user is excluded from results."""

    def setUp(self):
        """Set up a test user and log them in before each test."""
        self.user = _make_user('alice')
        self.client.login(username='alice', password='TestPass1!')

    def test_search_empty_query(self):
        """Test that searching with an empty query returns an empty list of users."""
        resp = self.client.get(reverse('search_users'), {'q': ''})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_no_query_param(self):
        """Test that searching without a 'q' query parameter returns an empty list of users."""
        resp = self.client.get(reverse('search_users'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_whitespace_only(self):
        """Test that searching with a query consisting only of whitespace returns an empty list of users."""
        resp = self.client.get(reverse('search_users'), {'q': '   '})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_search_finds_user_by_username(self):
        """Test that searching with a valid username query returns the correct user in the results."""
        _make_user('bob', first_name='Bob', last_name='Smith')
        resp = self.client.get(reverse('search_users'), {'q': 'bob'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('bob', usernames)

    def test_search_finds_user_by_first_name(self):
        """Test that searching with a valid first name query returns the correct user in the results."""
        _make_user('carol', first_name='Carol')
        resp = self.client.get(reverse('search_users'), {'q': 'Carol'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertIn('carol', usernames)

    def test_search_excludes_self(self):
        """Test that searching for the logged-in user's own username does not include them in the search results."""
        resp = self.client.get(reverse('search_users'), {'q': 'alice'})
        data = json.loads(resp.content)
        usernames = [u['username'] for u in data['users']]
        self.assertNotIn('alice', usernames)

    def test_search_no_results(self):
        """Test that searching with a query that does not match any users returns an empty list of users."""
        resp = self.client.get(reverse('search_users'), {'q': 'nonexistentuser123'})
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

class FollowersAPITests(TestCase):
    """Tests for the followers_api view, covering scenarios of no followers, having followers, follow-back status, and ensuring login is required to access the API."""

    def setUp(self):
        """Set up test users and log in before each test."""
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_followers_api_empty(self):
        """Test that the followers_api view returns an empty list of users when the logged-in user has no followers."""
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_followers_api_with_followers(self):
        """Test that the followers_api view returns the correct list of followers when the logged-in user has followers, and that the returned data includes the expected follower usernames."""
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_followers_api_includes_follow_back_info(self):
        """Test that the followers_api view includes the 'is_followed_back' field in the response data, indicating whether the logged-in user follows back each of their followers."""
        self.bob.following.add(self.alice)
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertTrue(data['users'][0]['is_followed_back'])

    def test_followers_api_not_followed_back(self):
        """Test that the followers_api view correctly indicates when the logged-in user does not follow back a follower by setting 'is_followed_back' to False in the response data."""
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('followers_api'))
        data = json.loads(resp.content)
        self.assertFalse(data['users'][0]['is_followed_back'])

    def test_followers_api_requires_login(self):
        """Test that the followers_api view requires the user to be logged in, and redirects to the login page if accessed without authentication."""
        self.client.logout()
        resp = self.client.get(reverse('followers_api'))
        self.assertEqual(resp.status_code, 302)

class FollowingAPITests(TestCase):
    """Tests for the following_api view, covering scenarios of not following anyone, having followings, and ensuring login is required to access the API."""

    def setUp(self):
        """Set up test users and log in before each test."""
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.client.login(username='alice', password='TestPass1!')

    def test_following_api_empty(self):
        """Test that the following_api view returns an empty list of users when the logged-in user is not following anyone."""
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_following_api_with_following(self):
        """Test that the following_api view returns the correct list of users that the logged-in user is following, and that the returned data includes the expected usernames."""
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('following_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_following_api_requires_login(self):
        """Test that the following_api view requires the user to be logged in, and redirects to the login page if accessed without authentication."""
        self.client.logout()
        resp = self.client.get(reverse('following_api'))
        self.assertEqual(resp.status_code, 302)


class FriendsAPITests(TestCase):
    """Tests for the friends_api view, covering scenarios of no friends, having mutual followers (friends), one-way following (not friends), and ensuring login is required to access the API."""

    def setUp(self):
        """Set up test users and log in before each test."""
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.charlie = _make_user('charlie')
        self.client.login(username='alice', password='TestPass1!')

    def test_friends_api_empty(self):
        """Test that the friends_api view returns an empty list of users when the logged-in user has no friends."""
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_mutual_follow(self):
        """Test that the friends_api view returns the correct list of users when the logged-in user has mutual followers (friends)."""
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(len(data['users']), 1)
        self.assertEqual(data['users'][0]['username'], 'bob')

    def test_friends_api_one_way_not_friend(self):
        """Test that the friends_api view does not include users who are only followed by the logged-in user but do not follow back."""
        self.alice.following.add(self.bob)
        resp = self.client.get(reverse('friends_api'))
        data = json.loads(resp.content)
        self.assertEqual(data['users'], [])

    def test_friends_api_requires_login(self):
        """Test that the friends_api view requires the user to be logged in, and redirects to the login page if accessed without authentication."""
        self.client.logout()
        resp = self.client.get(reverse('friends_api'))
        self.assertEqual(resp.status_code, 302)


class UserFollowersAPIPrivateTests(TestCase):
    """Tests for the followers_api and following_api views when accessing a private user's followers/following lists, covering access control based on follow status and ensuring appropriate HTTP status codes are returned."""

    def setUp(self):
        """Set up test users including a private user, and log in before each test."""
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_followers_api_private_forbidden(self):
        """Test that the followers_api view returns a 403 Forbidden status code when trying to access the followers of a private user that the logged-in user does not follow, and that the response contains an appropriate error message indicating the account is private."""
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_following_api_private_forbidden(self):
        """Test that the following_api view returns a 403 Forbidden status code when trying to access the following list of a private user that the logged-in user does not follow, and that the response contains an appropriate error message indicating the account is private."""
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)
        data = json.loads(resp.content)
        self.assertIn('private', data['error'].lower())

    def test_user_followers_api_private_allowed_if_following(self):
        """Test that the followers_api view returns a 200 OK status code and the correct followers data when accessing the followers of a private user that the logged-in user follows."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_private_allowed_if_following(self):
        """Test that the following_api view returns a 200 OK status code and the correct following data when accessing the following list of a private user that the logged-in user follows."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_own_profile_allowed(self):
        """Test that the followers_api view returns a 200 OK status code when accessing the followers of the logged-in user's own profile, regardless of privacy settings."""
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_followers_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_own_profile_allowed(self):
        """Test that the following_api view returns a 200 OK status code when accessing the following list of the logged-in user's own profile, regardless of privacy settings."""
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_following_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_followers_api_public_always_allowed(self):
        """Test that the followers_api view returns a 200 OK status code when accessing the followers of a public user, regardless of follow status."""
        _make_user('public_user', privacy_private=False)
        resp = self.client.get(reverse('user_followers_api', args=['public_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_following_api_public_always_allowed(self):
        """Test that the following_api view returns a 200 OK status code when accessing the following list of a public user, regardless of follow status."""
        _make_user('public_user', privacy_private=False)
        resp = self.client.get(reverse('user_following_api', args=['public_user']))
        self.assertEqual(resp.status_code, 200)

class UserFriendsAPIPrivateTests(TestCase):
    """Tests for the friends_api view when accessing a private user's friends list, covering access control based on follow status and ensuring appropriate HTTP status codes are returned."""

    def setUp(self):
        """Set up test users including a private user, and log in before each test."""
        self.alice = _make_user('alice')
        self.private_user = _make_user('private_user', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_user_friends_api_private_forbidden(self):
        """Test that the friends_api view returns a 403 Forbidden status code when trying to access the friends of a private user that the logged-in user does not follow, and that the response contains an appropriate error message indicating the account is private."""
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 403)

    def test_user_friends_api_private_allowed_if_following(self):
        """Test that the friends_api view returns a 200 OK status code and the correct friends data when accessing the friends of a private user that the logged-in user follows."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_own(self):
        """Test that the friends_api view returns a 200 OK status code when accessing the friends of the logged-in user's own profile, regardless of privacy settings."""
        self.client.login(username='private_user', password='TestPass1!')
        resp = self.client.get(reverse('user_friends_api', args=['private_user']))
        self.assertEqual(resp.status_code, 200)

    def test_user_friends_api_public(self):
        """Test that the friends_api view returns a 200 OK status code when accessing the friends of a public user, regardless of follow status."""
        _make_user('pubuser', privacy_private=False)
        resp = self.client.get(reverse('user_friends_api', args=['pubuser']))
        self.assertEqual(resp.status_code, 200)

class UserProfileViewTests(TestCase):
    """Tests for the user_profile view, covering access control based on privacy settings and follow status, as well as the presence of expected context variables in the profile view."""

    def setUp(self):
        """Set up test users including a private user, and log in before each test."""
        self.alice = _make_user('alice')
        self.bob = _make_user('bob')
        self.private_user = _make_user('private_carol', privacy_private=True)
        self.client.login(username='alice', password='TestPass1!')

    def test_view_public_user_profile(self):
        """Test that the user profile view for a public user is accessible and that the context indicates the profile can be viewed."""
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])

    def test_view_private_user_profile_not_following(self):
        """Test that the user profile view for a private user that the logged-in user does not follow is accessible but indicates the profile cannot be viewed."""
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['can_view'])

    def test_view_private_user_profile_following(self):
        """Test that the user profile view for a private user that the logged-in user follows is accessible and indicates the profile can be viewed, as well as confirming that the context reflects the following status."""
        self.alice.following.add(self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_view'])
        self.assertTrue(resp.context['is_following'])

    def test_view_profile_context_keys(self):
        """Test that the user profile view context contains the expected keys such as 'profile_user', 'posts', 'is_following', 'can_view', 'friends_count', 'has_pending_request', and 'incoming_requests'."""
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertIn('profile_user', resp.context)
        self.assertIn('posts', resp.context)
        self.assertIn('is_following', resp.context)
        self.assertIn('can_view', resp.context)
        self.assertIn('friends_count', resp.context)
        self.assertIn('has_pending_request', resp.context)
        self.assertIn('incoming_requests', resp.context)

    def test_view_profile_with_pending_request(self):
        """Test that the user profile view for a private user with a pending follow request from the logged-in user indicates the presence of the pending request in the context."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.private_user)
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertTrue(resp.context['has_pending_request'])

    def test_profile_friends_count(self):
        """Test that the friends count in the user profile context is accurate for a user with mutual followers (friends)."""
        self.alice.following.add(self.bob)
        self.bob.following.add(self.alice)
        resp = self.client.get(reverse('user_profile', args=['bob']))
        self.assertEqual(resp.context['friends_count'], 1)

    def test_profile_friends_count_private_not_viewable(self):
        """Test that the friends count for a private user that the logged-in user cannot view is zero."""
        resp = self.client.get(reverse('user_profile', args=['private_carol']))
        self.assertEqual(resp.context['friends_count'], 0)