from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.notification import Notification
from timeout.models.event import Event

User = get_user_model()


class NotificationModelTest(TestCase):
    """Tests for Notification model fields, methods, and constraints."""

    def setUp(self):
        """Set up test users, event, and notification for testing."""
        self.user = User.objects.create_user(
            username='recipient', password='pass123'
        )
        self.sender = User.objects.create_user(
            username='sender', password='pass123'
        )
        self.event = Event.objects.create(
            creator=self.user,
            title='Algorithms Exam',
            event_type=Event.EventType.EXAM,
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            end_datetime=timezone.now() + timezone.timedelta(days=1, hours=2),
        )
        self.notification = Notification.objects.create(
            user=self.user,
            title='⏰ Deadline: Assignment 1',
            message='1 day left to complete your deadline!',
            type=Notification.Type.DEADLINE,
            deadline=self.event,
        )

    def test_str_representation(self):
        """Test that the string representation includes the user's username and notification title."""
        result = str(self.notification)
        self.assertIn(self.user.username, result)
        self.assertIn('Deadline', result)

    #  Default values 

    def test_default_is_read_false(self):
        """Test that the default value of is_read is False."""
        self.assertFalse(self.notification.is_read)

    def test_default_is_dismissed_false(self):
        """Test that the default value of is_dismissed is False."""
        self.assertFalse(self.notification.is_dismissed)

    def test_default_type_is_deadline(self):
        """Test that the default value of type is DEADLINE."""
        n = Notification.objects.create(
            user=self.user,
            title='Test',
            message='Test message',
        )
        self.assertEqual(n.type, Notification.Type.DEADLINE)

    def test_created_at_auto_set(self):
        """Test that created_at is automatically set on creation."""
        self.assertIsNotNone(self.notification.created_at)

    #  Type choices 

    def test_all_type_choices_exist(self):
        """Test that all type choices exist."""
        expected_types = [
            'deadline', 'event', 'message', 'like',
            'comment', 'bookmark', 'follow',
            'exam', 'class', 'meeting', 'study_session',
        ]
        actual_values = [choice[0] for choice in Notification.Type.choices]
        for t in expected_types:
            self.assertIn(t, actual_values)

    def test_create_notification_each_type(self):
        """Test that a notification can be created with each type choice."""
        for type_value, _ in Notification.Type.choices:
            n = Notification.objects.create(
                user=self.user,
                title=f'Test {type_value}',
                message='Test',
                type=type_value,
            )
            self.assertEqual(n.type, type_value)

    #  deadline (Event) 

    def test_deadline_fk_set(self):
        """Test that the deadline foreign key is set correctly."""
        self.assertEqual(self.notification.deadline, self.event)

    def test_deadline_deleted_cascades_notification(self):
        """Test that deleting the linked event deletes the notification."""
        notif_id = self.notification.id
        self.event.delete()
        self.assertFalse(Notification.objects.filter(id=notif_id).exists())

    def test_deadline_nullable(self):
        """Test that the deadline field can be null."""
        n = Notification.objects.create(
            user=self.user,
            title='No event',
            message='No event linked',
            type=Notification.Type.MESSAGE,
        )
        self.assertIsNone(n.deadline)

    #  conversation 

    def test_conversation_nullable(self):
        """Test that the conversation field can be null."""
        self.assertIsNone(self.notification.conversation)

    #  post

    def test_post_nullable(self):
        """Test that the post field can be null."""
        self.assertIsNone(self.notification.post)

    #  is_read / is_dismissed 

    def test_mark_as_read(self):
        """Test that a notification can be marked as read."""
        self.notification.is_read = True
        self.notification.save(update_fields=['is_read'])
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_as_dismissed(self):
        """Test that a notification can be marked as dismissed."""
        self.notification.is_dismissed = True
        self.notification.save(update_fields=['is_dismissed'])
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_dismissed)

    #  Ordering 

    def test_ordering_newest_first(self):
        """Test that notifications are ordered by created_at descending."""
        older = Notification.objects.create(
            user=self.user,
            title='Old notification',
            message='Old',
            type=Notification.Type.DEADLINE,
        )
        newer = Notification.objects.create(
            user=self.user,
            title='New notification',
            message='New',
            type=Notification.Type.MESSAGE,
        )
        # Force distinct timestamps so ordering is deterministic
        Notification.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=1)
        )
        notifications = list(Notification.objects.filter(
            user=self.user, pk__in=[older.pk, newer.pk]
        ))
        self.assertEqual(notifications[0], newer)
        self.assertEqual(notifications[1], older)

    #  Filtering helpers
    def test_filter_unread(self):
        """Test that only unread notifications are returned."""
        Notification.objects.create(
            user=self.user,
            title='Read one',
            message='Already read',
            type=Notification.Type.MESSAGE,
            is_read=True,
        )
        unread = Notification.objects.filter(user=self.user, is_read=False)
        for n in unread:
            self.assertFalse(n.is_read)

    def test_filter_not_dismissed(self):
        """Test that only not dismissed notifications are returned."""
        Notification.objects.create(
            user=self.user,
            title='Dismissed',
            message='Gone',
            type=Notification.Type.MESSAGE,
            is_dismissed=True,
        )
        visible = Notification.objects.filter(user=self.user, is_dismissed=False)
        for n in visible:
            self.assertFalse(n.is_dismissed)

    def test_filter_by_type(self):
        """Test that notifications can be filtered by type."""
        Notification.objects.create(
            user=self.user,
            title='Like notif',
            message='Someone liked your post',
            type=Notification.Type.LIKE,
        )
        likes = Notification.objects.filter(user=self.user, type=Notification.Type.LIKE)
        self.assertTrue(likes.exists())
        for n in likes:
            self.assertEqual(n.type, Notification.Type.LIKE)

    #  Social notification types
    def test_like_notification_has_correct_type(self):
        """Test that a like notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='❤️ New Like',
            message='sender liked your post',
            type=Notification.Type.LIKE,
        )
        self.assertEqual(n.type, 'like')

    def test_comment_notification_has_correct_type(self):
        """Test that a comment notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='💬 sender commented on your post',
            message='Nice post!',
            type=Notification.Type.COMMENT,
        )
        self.assertEqual(n.type, 'comment')

    def test_bookmark_notification_has_correct_type(self):
        """Test that a bookmark notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='🏷️ New Bookmark',
            message='sender bookmarked your post',
            type=Notification.Type.BOOKMARK,
        )
        self.assertEqual(n.type, 'bookmark')

    def test_message_notification_has_correct_type(self):
        """Test that a message notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='💬 sender sent you a message',
            message='Hey!',
            type=Notification.Type.MESSAGE,
        )
        self.assertEqual(n.type, 'message')

    #  Event-type notifications 
    def test_exam_notification_type(self):
        """Test that an exam notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='📝 Exam: Algorithms',
            message='Your Exam starts tomorrow!',
            type=Notification.Type.EXAM,
            deadline=self.event,
        )
        self.assertEqual(n.type, 'exam')

    def test_class_notification_type(self):
        """Test that a class notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='🏫 Class: Maths',
            message='Your Class starts in 1 hour!',
            type=Notification.Type.CLASS,
        )
        self.assertEqual(n.type, 'class')

    def test_meeting_notification_type(self):
        """Test that a meeting notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='🤝 Meeting: Supervisor',
            message='Your Meeting starts tomorrow!',
            type=Notification.Type.MEETING,
        )
        self.assertEqual(n.type, 'meeting')

    def test_study_session_notification_type(self):
        """Test that a study session notification has the correct type."""
        n = Notification.objects.create(
            user=self.user,
            title='📚 Study Session: Revision',
            message='Your Study Session is coming up this week!',
            type=Notification.Type.STUDY_SESSION,
        )
        self.assertEqual(n.type, 'study_session')

    #  User isolation 
    def test_notifications_scoped_to_user(self):
        """Test that notifications are scoped to the correct user."""
        Notification.objects.create(
            user=self.sender,
            title='Other user notif',
            message='Not for recipient',
            type=Notification.Type.MESSAGE,
        )
        recipient_notifs = Notification.objects.filter(user=self.user)
        for n in recipient_notifs:
            self.assertEqual(n.user, self.user)