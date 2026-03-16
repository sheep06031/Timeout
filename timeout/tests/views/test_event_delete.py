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
        self.client = Client()
        self.user = User.objects.create_user(username='owner', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.event = make_event(self.user, title='My Event')
        self.url = reverse('event_delete', kwargs={'pk': self.event.pk})

    # ── Authentication ────────────────────────────────────────

    def test_login_required_redirects_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # ── Ownership ─────────────────────────────────────────────

    def test_other_user_gets_404(self):
        self.client.login(username='other', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete(self):
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('calendar'))
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    # ── Redirect & message ────────────────────────────────────

    def test_redirects_to_calendar_after_delete(self):
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('calendar'))

    def test_success_message_contains_event_title(self):
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url, follow=True)
        messages = list(response.context['messages'])
        self.assertTrue(any('My Event' in str(m) for m in messages))

    # ── Cascading deletes ─────────────────────────────────────

    def test_deletes_linked_notifications(self):
        Notification.objects.create(
            user=self.user,
            title='Deadline reminder',
            message='1 day left!',
            type=Notification.Type.DEADLINE,
            deadline=self.event,
        )
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertFalse(
            Notification.objects.filter(deadline=self.event).exists()
        )

    def test_deletes_multiple_notifications(self):
        for i in range(3):
            Notification.objects.create(
                user=self.user,
                title=f'Reminder {i}',
                message='Message',
                type=Notification.Type.DEADLINE,
                deadline=self.event,
            )
        self.assertEqual(Notification.objects.filter(deadline=self.event).count(), 3)
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertEqual(Notification.objects.filter(deadline=self.event).count(), 0)

    def test_event_deleted_from_db(self):
        self.client.login(username='owner', password='pass123')
        pk = self.event.pk
        self.client.get(self.url)
        self.assertFalse(Event.objects.filter(pk=pk).exists())

    def test_other_events_not_deleted(self):
        other_event = make_event(self.user, title='Keep Me')
        self.client.login(username='owner', password='pass123')
        self.client.get(self.url)
        self.assertTrue(Event.objects.filter(pk=other_event.pk).exists())

    def test_other_users_notifications_not_deleted(self):
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
        self.assertTrue(
            Notification.objects.filter(user=self.other).exists()
        )

    # ── Non-existent event ────────────────────────────────────

    def test_nonexistent_event_returns_404(self):
        self.client.login(username='owner', password='pass123')
        url = reverse('event_delete', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # ── Event types ───────────────────────────────────────────

    def test_delete_deadline_event(self):
        event = make_event(self.user, title='Deadline', event_type=Event.EventType.DEADLINE)
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_delete_exam_event(self):
        event = make_event(self.user, title='Exam', event_type=Event.EventType.EXAM)
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_delete_public_event_removes_linked_post(self):
        """Deleting a public event should remove its auto-generated post."""
        event = Event.objects.create(
            creator=self.user,
            title='Public Event',
            event_type=Event.EventType.OTHER,
            visibility=Event.Visibility.PUBLIC,
            start_datetime=timezone.now() + timezone.timedelta(hours=1),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
        )
        # Public event auto-creates a post via Event.save()
        self.assertTrue(event.posts.exists())
        url = reverse('event_delete', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.get(url)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())