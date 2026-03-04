import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models.message import Conversation, Message

User = get_user_model()

def make_user(username, password="testpass123"):
    return User.objects.create_user(username=username, password=password)

# Model tests
class ConversationModelTest(TestCase):

    def setUp(self):
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def test_str(self):
        self.assertEqual(str(self.conv), f"Conversation {self.conv.id}")

    def test_get_other_participant_returns_other_user(self):
        self.assertEqual(self.conv.get_other_participant(self.alice), self.bob)
        self.assertEqual(self.conv.get_other_participant(self.bob), self.alice)

    def test_get_last_message_none_when_empty(self):
        self.assertIsNone(self.conv.get_last_message())

    def test_get_last_message_returns_most_recent(self):
        m1 = Message.objects.create(conversation=self.conv, sender=self.alice, content="hi")
        m2 = Message.objects.create(conversation=self.conv, sender=self.bob,   content="hey")
        self.assertEqual(self.conv.get_last_message(), m2)

    def test_default_ordering_by_updated_at_desc(self):
        conv2 = Conversation.objects.create()
        conv2.participants.add(self.alice, self.bob)
        first = Conversation.objects.first()
        self.assertEqual(first, conv2)


class MessageModelTest(TestCase):

    def setUp(self):
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def test_message_creation(self):
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="Hello Bob!",
        )
        self.assertEqual(msg.content, "Hello Bob!")
        self.assertEqual(msg.sender, self.alice)
        self.assertFalse(msg.is_read)

    def test_message_str(self):
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="test",
        )
        self.assertIsInstance(str(msg), str)

    def test_message_default_is_read_false(self):
        msg = Message.objects.create(
            conversation=self.conv,
            sender=self.alice,
            content="unread",
        )
        self.assertFalse(msg.is_read)


# View tests

class InboxViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")

    def test_inbox_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("inbox"))
        self.assertIn(response.status_code, [301, 302])

    def test_inbox_accessible_when_logged_in(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertEqual(response.status_code, 200)

    def test_inbox_shows_users_conversations(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.alice, self.bob)

        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertContains(response, "bob")

    def test_inbox_does_not_show_unrelated_conversations(self):
        charlie = make_user("charlie")
        conv = Conversation.objects.create()
        conv.participants.add(self.bob, charlie)

        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("inbox"))
        self.assertNotContains(response, "charlie")


class StartConversationViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertIn(response.status_code, [301, 302])

    def test_creates_new_conversation(self):
        self.client.login(username="alice", password="testpass123")
        self.assertEqual(Conversation.objects.count(), 0)
        self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertEqual(Conversation.objects.count(), 1)

    def test_reuses_existing_conversation(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.alice, self.bob)

        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("start_conversation", args=["bob"]))
        self.assertEqual(Conversation.objects.count(), 1)

    def test_redirects_to_conversation_page(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["bob"]))
        conv = Conversation.objects.get()
        self.assertRedirects(response, reverse("conversation", args=[conv.id]))

    def test_starting_conversation_with_self_redirects_to_inbox(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["alice"]))
        self.assertRedirects(response, reverse("inbox"))

    def test_404_for_nonexistent_user(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("start_conversation", args=["nobody"]))
        self.assertEqual(response.status_code, 404)


class ConversationViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)
        Message.objects.create(conversation=self.conv, sender=self.bob, content="Hey Alice!")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertIn(response.status_code, [301, 302])

    def test_accessible_to_participant(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertEqual(response.status_code, 200)

    def test_403_or_404_for_non_participant(self):
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertIn(response.status_code, [403, 404])

    def test_messages_marked_as_read_on_view(self):
        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("conversation", args=[self.conv.id]))
        unread = Message.objects.filter(
            conversation=self.conv,
            sender=self.bob,
            is_read=False,
        ).count()
        self.assertEqual(unread, 0)

    def test_messages_from_self_not_marked_read(self):
        msg = Message.objects.create(
            conversation=self.conv, sender=self.alice, content="hi", is_read=False
        )
        self.client.login(username="alice", password="testpass123")
        self.client.get(reverse("conversation", args=[self.conv.id]))
        msg.refresh_from_db()
        self.assertFalse(msg.is_read)

    def test_shows_other_users_username(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("conversation", args=[self.conv.id]))
        self.assertContains(response, "bob")


class SendMessageViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

    def _url(self):
        return reverse("send_message", args=[self.conv.id])

    def test_redirects_when_not_logged_in(self):
        response = self.client.post(self._url(), {"content": "hi"})
        self.assertIn(response.status_code, [301, 302])

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_sends_message_successfully(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "Hello Bob!"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["content"], "Hello Bob!")
        self.assertEqual(data["sender"], "alice")
        self.assertTrue(data["is_me"])

    def test_message_saved_to_db(self):
        self.client.login(username="alice", password="testpass123")
        self.client.post(self._url(), {"content": "persisted?"})
        self.assertEqual(Message.objects.filter(content="persisted?").count(), 1)

    def test_empty_message_returns_400(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "   "})
        self.assertEqual(response.status_code, 400)

    def test_non_participant_cannot_send(self):
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.post(self._url(), {"content": "intruder"})
        self.assertIn(response.status_code, [403, 404])

    def test_response_contains_formatted_time(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(self._url(), {"content": "time check"})
        data = json.loads(response.content)
        self.assertIn("created_at", data)
        self.assertRegex(data["created_at"], r"^\d{2}:\d{2}$")


class PollMessagesViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.alice = make_user("alice")
        self.bob   = make_user("bob")
        self.conv  = Conversation.objects.create()
        self.conv.participants.add(self.alice, self.bob)

        self.m1 = Message.objects.create(
            conversation=self.conv, sender=self.bob, content="msg 1"
        )
        self.m2 = Message.objects.create(
            conversation=self.conv, sender=self.bob, content="msg 2"
        )

    def _url(self):
        return reverse("poll_messages", args=[self.conv.id])

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(self._url())
        self.assertIn(response.status_code, [301, 302])

    def test_returns_all_messages_when_last_id_zero(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 2)

    def test_returns_only_new_messages_after_last_id(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": self.m1.id})
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["content"], "msg 2")

    def test_is_me_flag_correct(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        data = json.loads(response.content)
        for msg in data["messages"]:
            self.assertFalse(msg["is_me"])

    def test_polled_messages_marked_as_read(self):
        self.client.login(username="alice", password="testpass123")
        self.client.get(self._url(), {"last_id": 0})
        unread = Message.objects.filter(
            conversation=self.conv, sender=self.bob, is_read=False
        ).count()
        self.assertEqual(unread, 0)

    def test_non_participant_cannot_poll(self):
        charlie = make_user("charlie")
        self.client.login(username="charlie", password="testpass123")
        response = self.client.get(self._url(), {"last_id": 0})
        self.assertIn(response.status_code, [403, 404])