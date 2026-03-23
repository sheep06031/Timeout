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
        self.alice = User.objects.create_user(username="alice", password="pass")
        self.bob   = User.objects.create_user(username="bob",   password="pass")
        self.bob.privacy_private = True
        self.bob.save()

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password="pass"))

    def follow_url(self, username):
        return reverse("follow_user", args=[username])

    # Public accounts

    def test_public_follow_is_direct(self):
        self.login(self.alice)
        res = self.client.post(self.follow_url(self.alice.username[0:0] or "alice"), follow=False)
        pub = User.objects.create_user(username="pub", password="pass")
        res = self.client.post(self.follow_url("pub"))
        data = json.loads(res.content)
        self.assertTrue(data["following"])
        self.assertFalse(data["requested"])
        self.assertTrue(self.alice.following.filter(username="pub").exists())

    def test_public_unfollow(self):
        self.login(self.alice)
        pub = User.objects.create_user(username="pub2", password="pass")
        self.alice.following.add(pub)
        res = self.client.post(self.follow_url("pub2"))
        data = json.loads(res.content)
        self.assertFalse(data["following"])
        self.assertFalse(self.alice.following.filter(username="pub2").exists())

    # Private accounts

    def test_private_follow_creates_request(self):
        self.login(self.alice)
        res = self.client.post(self.follow_url("bob"))
        data = json.loads(res.content)
        self.assertFalse(data["following"])
        self.assertTrue(data["requested"])
        self.assertTrue(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_private_follow_cancel_request(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.alice)
        res = self.client.post(self.follow_url("bob"))
        data = json.loads(res.content)
        self.assertFalse(data["requested"])
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    # Accept

    def test_accept_adds_follower(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(self.alice.following.filter(pk=self.bob.pk).exists())

    def test_accept_deletes_request(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_accept_creates_notification(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("accept_follow_request", args=["alice"]))
        self.assertTrue(Notification.objects.filter(
            user=self.alice,
            type=Notification.Type.FOLLOW,
        ).exists())

    # Reject

    def test_reject_deletes_request(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.post(reverse("reject_follow_request", args=["alice"]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(FollowRequest.objects.filter(
            from_user=self.alice, to_user=self.bob
        ).exists())

    def test_reject_does_not_add_follower(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        self.client.post(reverse("reject_follow_request", args=["alice"]))
        self.assertFalse(self.alice.following.filter(pk=self.bob.pk).exists())

    # Profile context 

    def test_profile_shows_pending_request(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.alice)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertTrue(res.context["has_pending_request"])

    def test_profile_no_pending_when_none(self):
        self.login(self.alice)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertFalse(res.context["has_pending_request"])

    def test_own_profile_shows_incoming_requests(self):
        FollowRequest.objects.create(from_user=self.alice, to_user=self.bob)
        self.login(self.bob)
        res = self.client.get(reverse("user_profile", args=["bob"]))
        self.assertIn(
            self.alice,
            [fr.from_user for fr in res.context["incoming_requests"]]
        )

    # Self follow 
    def test_self_follow_rejected(self):
        self.login(self.alice)
        res = self.client.post(self.follow_url("alice"))
        self.assertEqual(res.status_code, 400)
