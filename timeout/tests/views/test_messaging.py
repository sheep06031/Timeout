import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models.message import Conversation, Message
User = get_user_model()

def make_user(username, password="testpass123"):
    """Helper function to create a user with the given username and password."""
    return User.objects.create_user(username=username, password=password)

class ConversationModelTest(TestCase):
    """Tests for the Conversation model."""
    def setUp(self):
        """Create two users and a conversation for testing."""
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def test_str(self):
        """The string representation of a conversation should include its ID."""
        self.assertEqual(str(self.conv), f"Conversation {self.conv.id}")

    def test_get_other_participant_returns_other_user(self):
        """get_other_participant should return the other user in the conversation."""
        self.assertEqual(self.conv.get_other_participant(self.alice), self.bob)
        self.assertEqual(self.conv.get_other_participant(self.bob), self.alice)

    def test_get_last_message_none_when_empty(self):
        """get_last_message should return None if there are no messages in the conversation."""
        self.assertIsNone(self.conv.get_last_message())

    def test_get_last_message_returns_most_recent(self):
        """get_last_message should return the most recently created message."""
        Message.objects.create(conversation=self.conv, sender=self.alice, content="hi")
        m2 = Message.objects.create(conversation=self.conv, sender=self.bob, content="hey")
        last = self.conv.get_last_message()
        self.assertEqual(last.content, m2.content)

    def test_default_ordering_by_updated_at_desc(self):
        """Conversations should be ordered by updated_at descending by default."""
        conv2 = Conversation.objects.create()
        conv2.participants.add(self.alice, self.bob)
        ids = list(Conversation.objects.values_list('id', flat=True))
        self.assertIn(conv2.id, ids)
        self.assertIn(self.conv.id, ids)

class MessageModelTest(TestCase):
    """Tests for the Message model."""
    def setUp(self):
        """Create two users and a conversation for testing."""
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def test_message_creation(self):
        """A message should be created with the correct content, sender, and default is_read value."""
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="Hello Bob!",
        )
        self.assertEqual(msg.content, "Hello Bob!")
        self.assertEqual(msg.sender, self.alice)
        self.assertFalse(msg.is_read)

    def test_message_str(self):
        """The string representation of a message should include the sender's username and a snippet of the content."""
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="test",
        )
        self.assertIsInstance(str(msg), str)

    def test_message_default_is_read_false(self):
        """When a message is created, is_read should default to False."""
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="unread",
        )
        self.assertFalse(msg.is_read)

class InboxViewTest(TestCase):
    """Tests for the inbox view."""
    def setUp(self):
        """Create two users and a conversation for testing."""
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")

    def test_inbox_redirects_when_not_logged_in(self):
        """The inbox view should redirect to login for unauthenticated users."""
        response = self.client.get(reverse("inbox"))
        self.assertIn(response.status_code, [301, 302])

    def test_inbox_accessible_when_logged_in(self):
        """The inbox view should be accessible to logged-in users."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertEqual(response.status_code, 200)

    def test_inbox_shows_users_conversations(self):
        """The inbox should show conversations that the logged-in user is a participant in."""
        conv = Conversation.objects.create()
        conv.participants.add(self.alice, self.bob)

        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertContains(response, "bob")

    def test_inbox_does_not_show_unrelated_conversations(self):
        """The inbox should not show conversations that the logged-in user is not a participant in."""
        charlie = make_user("charlie")
        conv = Conversation.objects.create()
        conv.participants.add(self.bob, charlie)

        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertNotContains(response, "charlie")

class StartConversationViewTest(TestCase):
    """Tests for the start_conversation view."""
    def setUp(self):
        """Create two users for testing."""
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")

    def test_redirects_when_not_logged_in(self):
        """The start_conversation view should redirect to login for unauthenticated users."""
        response = self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertIn(response.status_code, [301, 302])

    def test_creates_new_conversation(self):
        """If no existing conversation exists between the two users, it should create a new one."""
        self.client.login(username="alice", password="testpass123")
        self.assertEqual(Conversation.objects.count(), 0)
        self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertEqual(Conversation.objects.count(), 1)

    def test_reuses_existing_conversation(self):
        """If a conversation already exists between the two users, it should reuse it instead of creating a new one."""
        conv = Conversation.objects.create()
        conv.participants.add(self.alice, self.bob)

        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertEqual(Conversation.objects.count(), 1)

    def test_redirects_to_conversation_page(self):
        """After starting a conversation, it should redirect to the conversation page."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["bob"]))
        conv = Conversation.objects.get()
        self.assertRedirects(response, reverse("conversation", args=[conv.id]))

    def test_starting_conversation_with_self_redirects_to_inbox(self):
        """If a user tries to start a conversation with themselves, it should redirect to the inbox instead of creating a conversation."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["alice"]))
        self.assertRedirects(response, reverse("inbox"))

    def test_404_for_nonexistent_user(self):
        """If the username provided does not exist, it should return a 404 error."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["nobody"]))
        self.assertEqual(response.status_code, 404)

class ConversationViewTest(TestCase):
    """Tests for the conversation view."""
    def setUp(self):
        """Create two users and a conversation for testing."""
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)
        Message.objects.create(conversation=self.conv, sender=self.bob, content="Hey Alice!")

    def test_redirects_when_not_logged_in(self):
        """The conversation view should redirect to login for unauthenticated users."""
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertIn(response.status_code, [301, 302])

    def test_accessible_to_participant(self):
        """The conversation view should be accessible to users who are participants in the conversation."""
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertEqual(response.status_code, 200)

    def test_403_or_404_for_non_participant(self):
        """"The conversation view should return a 403 or 404 error for users who are not participants in the conversation."""
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertIn(response.status_code, [403, 404])

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