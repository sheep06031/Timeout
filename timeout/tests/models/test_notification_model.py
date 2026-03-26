from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.notification import Notification
from timeout.models.event import Event

User = get_user_model()


class NotificationModelTest(TestCase):
    """Tests for Notification model fields, methods, and constraints."""

    def setUp(self):
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

    #  __str__ 

    def test_str_representation(self):
        result = str(self.notification)
        self.assertIn(self.user.username, result)
        self.assertIn('Deadline', result)

    #  Default values 

    def test_default_is_read_false(self):
        self.assertFalse(self.notification.is_read)

    def test_default_is_dismissed_false(self):
        self.assertFalse(self.notification.is_dismissed)

    def test_default_type_is_deadline(self):
        n = Notification.objects.create(
            user=self.user,
            title='Test',
            message='Test message',
        )
        self.assertEqual(n.type, Notification.Type.DEADLINE)

    def test_created_at_auto_set(self):
        self.assertIsNotNone(self.notification.created_at)

    #  Type choices 

    def test_all_type_choices_exist(self):
        expected_types = [
            'deadline', 'event', 'message', 'like',
            'comment', 'bookmark', 'follow',
            'exam', 'class', 'meeting', 'study_session',
        ]
        actual_values = [choice[0] for choice in Notification.Type.choices]
        for t in expected_types:
            self.assertIn(t, actual_values)

    def test_create_notification_each_type(self):
        for type_value, _ in Notification.Type.choices:
            n = Notification.objects.create(
                user=self.user,
                title=f'Test {type_value}',
                message='Test',
                type=type_value,
            )
            self.assertEqual(n.type, type_value)

    #  FK: deadline (Event) 

    def test_deadline_fk_set(self):
        self.assertEqual(self.notification.deadline, self.event)

    def test_deadline_deleted_cascades_notification(self):
        notif_id = self.notification.id
        self.event.delete()
        self.assertFalse(Notification.objects.filter(id=notif_id).exists())

    def test_deadline_nullable(self):
        n = Notification.objects.create(
            user=self.user,
            title='No event',
            message='No event linked',
            type=Notification.Type.MESSAGE,
        )
        self.assertIsNone(n.deadline)

    #  FK: conversation 

    def test_conversation_nullable(self):
        self.assertIsNone(self.notification.conversation)

    #  FK: post ─

    def test_post_nullable(self):
        self.assertIsNone(self.notification.post)

    #  is_read / is_dismissed 

    def test_mark_as_read(self):
        self.notification.is_read = True
        self.notification.save(update_fields=['is_read'])
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_as_dismissed(self):
        self.notification.is_dismissed = True
        self.notification.save(update_fields=['is_dismissed'])
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_dismissed)

    #  Ordering 

    def test_ordering_newest_first(self):
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

    #  Filtering helpers ─

    def test_filter_unread(self):
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

    #  Social notification types ─

    def test_like_notification_has_correct_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='❤️ New Like',
            message='sender liked your post',
            type=Notification.Type.LIKE,
        )
        self.assertEqual(n.type, 'like')

    def test_comment_notification_has_correct_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='💬 sender commented on your post',
            message='Nice post!',
            type=Notification.Type.COMMENT,
        )
        self.assertEqual(n.type, 'comment')

    def test_bookmark_notification_has_correct_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='🏷️ New Bookmark',
            message='sender bookmarked your post',
            type=Notification.Type.BOOKMARK,
        )
        self.assertEqual(n.type, 'bookmark')

    def test_message_notification_has_correct_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='💬 sender sent you a message',
            message='Hey!',
            type=Notification.Type.MESSAGE,
        )
        self.assertEqual(n.type, 'message')

    #  Event-type notifications 

    def test_exam_notification_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='📝 Exam: Algorithms',
            message='Your Exam starts tomorrow!',
            type=Notification.Type.EXAM,
            deadline=self.event,
        )
        self.assertEqual(n.type, 'exam')

    def test_class_notification_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='🏫 Class: Maths',
            message='Your Class starts in 1 hour!',
            type=Notification.Type.CLASS,
        )
        self.assertEqual(n.type, 'class')

    def test_meeting_notification_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='🤝 Meeting: Supervisor',
            message='Your Meeting starts tomorrow!',
            type=Notification.Type.MEETING,
        )
        self.assertEqual(n.type, 'meeting')

    def test_study_session_notification_type(self):
        n = Notification.objects.create(
            user=self.user,
            title='📚 Study Session: Revision',
            message='Your Study Session is coming up this week!',
            type=Notification.Type.STUDY_SESSION,
        )
        self.assertEqual(n.type, 'study_session')

    #  User isolation 

    def test_notifications_scoped_to_user(self):
        Notification.objects.create(
            user=self.sender,
            title='Other user notif',
            message='Not for recipient',
            type=Notification.Type.MESSAGE,
        )
        recipient_notifs = Notification.objects.filter(user=self.user)
        for n in recipient_notifs:
            self.assertEqual(n.user, self.user)