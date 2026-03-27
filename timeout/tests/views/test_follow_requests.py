import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models import FollowRequest
from timeout.models.notification import Notification

User = get_user_model()


class FollowRequestTest(TestCase):
    """
    Tests for the follow request system

    """

    def setUp(self):
        """Create two users, one public and one private, for testing."""
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob   = User.objects.create_user(username="bob",   password="pass")
        self.bob.privacy_private = True
        self.bob.save()

    def login(self, user):
        """Helper method to log in a user."""
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def follow_url(self, username):
        """Helper method to get the URL for following a user."""
        return reverse("follow_user", args=[username])


    def test_public_follow_is_direct(self):
        """Following a public user should immediately create a follower relationship."""
        self.login(self.alice)
        res = self.client.post(self.follow_url(self.alice.username[0:0] or "alice"), follow=False)
        pub = User.objects.create_user(username="pub", password="pass")
        res = self.client.post(self.follow_url("pub"))
        data = json.loads(res.content)
        self.assertTrue(data["following"])
        self.assertFalse(data["requested"])
        self.assertTrue(self.alice.following.filter(username="pub").exists())

    def test_public_unfollow(self):
        """Unfollowing a public user should remove the follower relationship."""
        self.login(self.alice)
        pub = User.objects.create_user(username="pub2", password="pass")
        self.alice.following.add(pub)
        res = self.client.post(self.follow_url("pub2"))
        data = json.loads(res.content)
        self.assertFalse(data["following"])
        self.assertFalse(self.alice.following.filter(username="pub2").exists())


    def test_private_follow_creates_request(self):
        """Following a private user should create a FollowRequest, not a follower relationship."""
        self.login(self.alice)
        res = self.client.post(self.follow_url("bob"))
        data = json.loads(res.content)
        self.assertFalse(data["following"])
        self.assertTrue(data["requested"])
        self.assertTrue(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_private_follow_cancel_request(self):
        """If a follow request already exists, posting to follow again should cancel the request."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.alice)
        res = self.client.post(self.follow_url("bob"))
        data = json.loads(res.content)
        self.assertFalse(data["requested"])
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_accept_adds_follower(self):
        """Accepting a follow request should create a follower relationship."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(self.alice.following.filter(pk=self.bob.pk).exists())

    def test_accept_deletes_request(self):
        """Accepting a follow request should delete the FollowRequest object."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_accept_creates_notification(self):
        """Accepting a follow request should notify the requester that their request was accepted."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertTrue(Notification.objects.filter(
            user=self.alice,
            type=Notification.Type.FOLLOW,
        ).exists())

    def test_reject_deletes_request(self):
        """Rejecting a follow request should delete the FollowRequest object."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.post(reverse("reject_follow_request", args=["alice"]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_reject_does_not_add_follower(self):
        """Rejecting a follow request should not create a follower relationship."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("reject_follow_request", args=["alice"]))
        self.assertFalse(self.alice.following.filter(pk=self.bob.pk).exists())

    def test_profile_shows_pending_request(self):
        """If there is a pending follow request from the logged-in user to the profile being viewed, it should be indicated in the context."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.alice)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertTrue(res.context["has_pending_request"])

    def test_profile_no_pending_when_none(self):
        """If there are no pending follow requests from the logged-in user to the profile being viewed, it should be indicated in the context."""
        self.login(self.alice)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertFalse(res.context["has_pending_request"])

    def test_own_profile_shows_incoming_requests(self):
        """When viewing their own profile, a user should see a list of incoming follow requests."""
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertIn(
            self.alice,
            [fr.from_user for fr in res.context["incoming_requests"]]
        )

    def test_self_follow_rejected(self):
        """A user should not be able to follow themselves."""
        self.login(self.alice)
        res = self.client.post(self.follow_url("alice"))
        self.assertEqual(res.status_code, 400)
