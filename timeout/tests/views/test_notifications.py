from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.notification import Notification
from timeout.models.event import Event

User = get_user_model()


def make_notification(user, title='Test', message='Test message',
                      notif_type=Notification.Type.DEADLINE,
                      is_read=False, is_dismissed=False, event=None):
    """Helper to create a notification."""
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        type=notif_type,
        is_read=is_read,
        is_dismissed=is_dismissed,
        deadline=event,
    )


class NotificationsViewTests(TestCase):
    """Tests for notifications_view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('notifications')

    def test_login_required_redirects_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_renders_notifications_page(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/notifications.html')

    def test_shows_only_own_notifications(self):
        make_notification(self.user, title='Mine')
        make_notification(self.other, title='Not Mine')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Mine')

    def test_dismissed_notifications_not_shown(self):
        make_notification(self.user, title='Visible')
        make_notification(self.user, title='Dismissed', is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Visible')

    def test_unread_count_in_context(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['unread_count'], 2)

    def test_filter_unread_only(self):
        make_notification(self.user, title='Unread', is_read=False)
        make_notification(self.user, title='Read', is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?filter=unread')
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Unread')

    def test_filter_param_in_context(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?filter=unread')
        self.assertEqual(response.context['current_filter'], 'unread')

    def test_no_filter_shows_all_non_dismissed(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context['notifications'])), 2)

    def test_pagination_10_per_page(self):
        for i in range(15):
            make_notification(self.user, title=f'Notif {i}')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context['notifications'])), 10)

    def test_empty_notifications(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['notifications'])), 0)


class MarkNotificationReadTests(TestCase):
    """Tests for mark_notification_read."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='Unread', is_read=False)
        self.url = reverse('mark_notification_read', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_notification_as_read(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_mark_read(self):
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        self.client.login(username='user', password='pass123')
        url = reverse('mark_notification_read', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_already_read_notification_stays_read(self):
        self.notif.is_read = True
        self.notif.save()
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)


class DeleteNotificationTests(TestCase):
    """Tests for delete_notification (sets is_dismissed=True)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='To Delete')
        self.url = reverse('delete_notification', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_sets_is_dismissed_true(self):
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_dismissed)

    def test_sets_is_read_true(self):
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_delete(self):
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_dismissed)

    def test_nonexistent_notification_returns_404(self):
        self.client.login(username='user', password='pass123')
        url = reverse('delete_notification', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_notification_not_removed_from_db(self):
        """Dismissing should soft-delete, not hard-delete."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(Notification.objects.filter(pk=self.notif.pk).exists())


class PollNotificationsTests(TestCase):
    """Tests for poll_notifications."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.url = reverse('poll_notifications')

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_returns_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_returns_notifications_and_unread_count(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        data = response.json()
        self.assertIn('notifications', data)
        self.assertIn('unread_count', data)

    def test_returns_only_new_notifications_after_last_id(self):
        n1 = make_notification(self.user, title='Old')
        n2 = make_notification(self.user, title='New')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + f'?last_id={n1.pk}')
        data = response.json()
        ids = [n['id'] for n in data['notifications']]
        self.assertNotIn(n1.pk, ids)
        self.assertIn(n2.pk, ids)

    def test_dismissed_notifications_excluded(self):
        n = make_notification(self.user, title='Dismissed', is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        data = response.json()
        ids = [item['id'] for item in data['notifications']]
        self.assertNotIn(n.pk, ids)

    def test_notification_fields_present(self):
        make_notification(self.user, title='My Notif', message='Hello')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        data = response.json()
        self.assertTrue(len(data['notifications']) > 0)
        notif = data['notifications'][0]
        self.assertIn('id', notif)
        self.assertIn('title', notif)
        self.assertIn('message', notif)
        self.assertIn('created_at', notif)
        self.assertIn('is_read', notif)

    def test_unread_count_correct(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        data = response.json()
        self.assertEqual(data['unread_count'], 2)

    def test_invalid_last_id_defaults_to_zero(self):
        make_notification(self.user, title='Test')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=notanumber')
        self.assertEqual(response.status_code, 200)

    def test_only_own_notifications_returned(self):
        other = User.objects.create_user(username='other', password='pass')
        make_notification(other, title='Not Mine')
        n = make_notification(self.user, title='Mine')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        data = response.json()
        ids = [item['id'] for item in data['notifications']]
        self.assertIn(n.pk, ids)
        self.assertEqual(len(ids), 1)