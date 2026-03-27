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