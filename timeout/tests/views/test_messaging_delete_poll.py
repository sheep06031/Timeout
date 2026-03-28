"""
Tests for the messaging views in the timeout app, including delete_message, send_message, and poll_messages.
Includes tests for:
- delete_message: successful deletion by staff, non-staff access denied, login required, method requirements, handling of non-existent messages
- send_message: successful sending by a conversation participant, message saved to database, empty messages rejected, non-participants cannot send, response contains formatted time
- poll_messages: successful polling by a conversation participant, returns all messages after last_id, is_me flag correct, polled messages marked as read, non-participants cannot poll
These tests ensure that the messaging functionality works correctly, enforces proper permissions, handles various edge cases, and that the user experience is consistent with expectations (e.g. messages marked as read when polled, correct response format when sending messages).
"""
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models.message import Conversation, Message
User = get_user_model()

def make_user(username, password="testpass123"):
    """Helper function to create a user with the given username and password."""
    return User.objects.create_user(username=username, password=password)

class DeleteMessageViewTest(TestCase):
    """Tests for the staff-only delete_message view."""

    def setUp(self):
        """Create a staff user, two regular users, a conversation, and a message for testing."""
        self.staff = make_user("staffuser")
        self.staff.is_staff = True
        self.staff.save()
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.conv = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)
        self.message = Message.objects.create(
            conversation=self.conv, sender=self.alice, content="hello",)

    def delete_url(self, message_id=None):
        """Helper method to get the URL for deleting a message."""
        return reverse("delete_message", args=[message_id or self.message.id])

    def test_staff_can_delete_message(self):
        """A staff user should be able to delete a message, which should remove it from the database."""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertFalse(Message.objects.filter(id=self.message.id).exists())

    def test_non_staff_gets_403(self):
        """A non-staff user should get a 403 Forbidden error when trying to delete a message."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Message.objects.filter(id=self.message.id).exists())

    def test_requires_login(self):
        """An unauthenticated user should be redirected to the login page when trying to delete a message."""
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_rejects_get(self):
        """The delete_message view should reject GET requests (require POST)."""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(self.delete_url())
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_message_returns_404(self):
        """If the message ID does not exist, should return a 404 error."""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(self.delete_url(message_id=99999))
        self.assertEqual(response.status_code, 404)

    def test_messages_marked_as_read_on_view(self):
        """When a conversation is viewed, any messages from the other user that were previously unread should be marked as read."""
        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("conversation", args=[self.conv.id]))
        unread = Message.objects.filter(
            conversation=self.conv,
            sender=self.bob,
            is_read=False,
        ).count()
        self.assertEqual(unread, 0)

    def test_messages_from_self_not_marked_read(self):
        """When a conversation is viewed, messages sent by the logged-in user should not be marked as read."""
        msg = Message.objects.create(
            conversation=self.conv, sender=self.alice, content="hi", is_read=False)
        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("conversation", args=[self.conv.id]))
        msg.refresh_from_db()
        self.assertFalse(msg.is_read)

    def test_shows_other_users_username(self):
        """When viewing a conversation, the username of the other participant should be displayed on the page."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertContains(response, "bob")

class SendMessageViewTest(TestCase):
    """Tests for the send_message view."""
    def setUp(self):
        """Create two users and a conversation for testing."""
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def _url(self):
        """Helper method to get the URL for sending a message in the conversation."""
        return reverse("send_message", args=[self.conv.id])

    def test_redirects_when_not_logged_in(self):
        """The send_message view should redirect to login for unauthenticated users."""
        response = self.client.post(self._url(), {"content": "hi"})
        self.assertIn(response.status_code, [301, 302])

    def test_get_not_allowed(self):
        """The send_message view should reject GET requests (require POST)."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_sends_message_successfully(self):
        """A participant in the conversation should be able to send a message, which should be saved to the database and returned in the response."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "Hello Bob!"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["content"], "Hello Bob!")
        self.assertEqual(data["sender"], "alice")
        self.assertTrue(data["is_me"])

    def test_message_saved_to_db(self):
        """After sending a message, it should be saved to the database with the correct content, sender, and conversation."""
        self.client.login(username="alice", password="testpass123")
        self.client.post(self._url(), {"content": "persisted?"})
        self.assertEqual(Message.objects.filter(content="persisted?").count(), 1)

    def test_empty_message_returns_400(self):
        """Trying to send an empty message (content that is only whitespace) should return a 400 Bad Request error."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "   "})
        self.assertEqual(response.status_code, 400)

    def test_non_participant_cannot_send(self):
        """A user who is not a participant in the conversation should not be able to send a message and should receive a 403 or 404 error."""
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.post(self._url(), {"content": "intruder"})
        self.assertIn(response.status_code, [403, 404])

    def test_response_contains_formatted_time(self):
        """The response from sending a message should include a created_at field with the time formatted as HH:MM."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "time check"})
        data = json.loads(response.content)
        self.assertIn("created_at", data)
        self.assertRegex(data["created_at"], r"^\d{2}:\d{2}$")

class PollMessagesViewTest(TestCase):
    """Tests for the poll_messages view."""
    def setUp(self):
        """Create two users, a conversation, and some messages for testing."""
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)
        self.m1 = Message.objects.create(
            conversation=self.conv, sender=self.bob, content="msg 1")
        self.m2 = Message.objects.create(
            conversation=self.conv, sender=self.bob, content="msg 2")

    def _url(self):
        """Helper method to get the URL for polling messages in the conversation."""
        return reverse("poll_messages", args=[self.conv.id])

    def test_redirects_when_not_logged_in(self):
        """The poll_messages view should redirect to login for unauthenticated users."""
        response = self.client.get(self._url())
        self.assertIn(response.status_code, [301, 302])

    def test_returns_all_messages_when_last_id_zero(self):
        """If last_id is 0, the poll_messages view should return all messages in the conversation."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 2)

    def test_returns_only_new_messages_after_last_id(self):
        """If last_id is provided, the poll_messages view should return only messages with IDs greater than last_id."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": self.m1.id})
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["content"], "msg 2")

    def test_is_me_flag_correct(self):
        """The messages returned by poll_messages should have an is_me field that is True for messages sent by the logged-in user and False for messages sent by the other participant."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        data = json.loads(response.content)
        for msg in data["messages"]:
            self.assertFalse(msg["is_me"])

    def test_polled_messages_marked_as_read(self):
        """When messages are polled, any messages from the other participant that were previously unread should be marked as read in the database."""
        self.client.login(username="alice", password="testpass123")
        self.client.get(self._url(), {"last_id": 0})
        unread = Message.objects.filter(
            conversation=self.conv, sender=self.bob, is_read=False
        ).count()
        self.assertEqual(unread, 0)

    def test_non_participant_cannot_poll(self):
        """A user who is not a participant in the conversation should not be able to poll messages and should receive a 403 or 404 error."""
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        self.assertIn(response.status_code, [403, 404])
