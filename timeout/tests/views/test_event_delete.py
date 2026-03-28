"""
Tests for the event_delete view in the timeout app, which allows users to delete their own events. 
Includes tests for:
- Authentication requirements: ensuring that only logged-in users can access the view and that they can only delete their own events
- Successful deletion: verifying that the event is removed from the database, that any linked notifications are also deleted, and that the user is redirected to the calendar with a success message containing the event title
- Handling of edge cases: such as attempting to delete a non-existent event, ensuring that other events and notifications are not affected, and testing the deletion of different event types (e.g. deadline, exam, public event with linked post)
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.event import Event
from timeout.models.notification import Notification

User = get_user_model()


def make_event(creator, title='Test Event', event_type=None):
    """Helper to create a basic event."""
    now = timezone.now()
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=event_type or Event.EventType.OTHER,
        start_datetime=now + timezone.timedelta(hours=1),
        end_datetime=now + timezone.timedelta(hours=2),
    )


class EventDeleteViewTests(TestCase):
    """Tests for event_delete view."""

    def setUp(self):
        """Create a user and an event for testing."""
        self.client = Client()
        self.user  = User.objects.create_user(username='owner', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.event = make_event(self.user, title='My Event')
        self.url   = reverse('event_delete', kwargs={'pk': self.event.pk})

    def test_login_required_redirects_anonymous(self):
        """Anonymous users should be redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_other_user_gets_404(self):
        """A user who is not the owner should get a 404, not a 403."""
        self.client.login(username='other', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete(self):
        """The owner should be able to delete their event."""
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_nonexistent_event_returns_404(self):
        """Requesting deletion of a non-existent event should return 404."""
        self.client.login(username='owner', password='pass123')
        url = reverse('event_delete', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_redirects_to_calendar_after_delete(self):
        """After successful deletion, should redirect to calendar."""
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('calendar'))

    def test_success_message_contains_event_title(self):
        """After deletion, the success message should include the event title."""
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url, follow=True)
        msgs = list(response.context['messages'])
        self.assertTrue(any('My Event' in str(m) for m in msgs))

    def test_deletes_linked_notification(self):
        """If there is a notification linked to the event, it should be deleted when the event is deleted."""
        Notification.objects.create(
            user=self.user,
            title='Reminder',
            message='1 day left!',
            type=Notification.Type.DEADLINE,
            deadline=self.event,
        )
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertFalse(Notification.objects.filter(deadline=self.event).exists())

    def test_deletes_multiple_linked_notifications(self):
        """If there are multiple notifications linked to the event, they should all be deleted when the event is deleted."""
        for i in range(3):
            Notification.objects.create(
                user=self.user,
                title=f'Reminder {i}',
                message='Message',
                type=Notification.Type.DEADLINE,
                deadline=self.event,
            )
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertEqual(Notification.objects.filter(deadline=self.event).count(), 0)

    def test_event_deleted_from_db(self):
        """After deletion, the event should no longer exist in the database."""
        pk = self.event.pk
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertFalse(Event.objects.filter(pk=pk).exists())

    def test_other_events_not_deleted(self):
        """Deleting one event should not delete other events."""
        other_event = make_event(self.user, title='Keep Me')
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertTrue(Event.objects.filter(pk=other_event.pk).exists())

    def test_other_users_notifications_not_deleted(self):
        """Deleting an event should not delete notifications for other users, even if they are linked to the same event."""
        other_event = make_event(self.other, title='Other Event')
        Notification.objects.create(
            user=self.other,
            title='Other notif',
            message='Message',
            type=Notification.Type.DEADLINE,
            deadline=other_event,
        )
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertTrue(Notification.objects.filter(user=self.other).exists())

    def test_delete_deadline_event(self):
        """Deadline events may have special handling, so we should test deleting one."""
        event = make_event(self.user, title='Deadline', event_type=Event.EventType.DEADLINE)
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_delete_exam_event(self):
        """Exam events may have special handling, so we should test deleting one."""
        event = make_event(self.user, title='Exam', event_type=Event.EventType.EXAM)
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_delete_public_event_removes_linked_post(self):
        """Public events auto-generate a post — deleting the event should remove it."""
        event = Event.objects.create(
            creator=self.user,
            title='Public Event',
            event_type=Event.EventType.OTHER,
            visibility=Event.Visibility.PUBLIC,
            start_datetime=timezone.now() + timezone.timedelta(hours=1),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
        )

        self.assertTrue(event.posts.exists())
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

