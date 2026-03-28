"""
Tests for the notification views in the timeout app, including delete_notification, delete_all_notifications, and poll_notifications.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from timeout.models.notification import Notification

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


class DeleteNotificationTests(TestCase):
    """Tests for delete_notification (soft delete via is_dismissed=True)."""

    def setUp(self):
        """Create a user and a notification for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='To Delete')
        self.url = reverse('delete_notification', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        """Deleting a notification requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_sets_is_dismissed_true(self):
        """A user should be able to delete (dismiss) their own notification, which sets is_dismissed=True."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_dismissed)

    def test_sets_is_read_true(self):
        """When a notification is deleted (dismissed), it should also be marked as read (is_read=True) to ensure it doesn't show up as an unread notification."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_returns_success_json(self):
        """After deleting (dismissing), should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_delete(self):
        """A user should not be able to delete (dismiss) another user's notification (should return 404)."""
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_dismissed)

    def test_nonexistent_notification_returns_404(self):
        """ If the notification ID does not exist, should return a 404 error."""
        self.client.login(username='user', password='pass123')
        url = reverse('delete_notification', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_notification_not_removed_from_db(self):
        """Dismissing should soft-delete, not hard-delete."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(Notification.objects.filter(pk=self.notif.pk).exists())


class DeleteAllNotificationsTests(TestCase):
    """Tests for delete_all_notifications."""

    def setUp(self):
        """Create a user for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('delete_all_notifications')

    def test_login_required(self):
        """Deleting all notifications requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_dismisses_all_notifications(self):
        """ When a user deletes all notifications, all of their notifications should be marked as dismissed (is_dismissed=True)."""
        make_notification(self.user)
        make_notification(self.user)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_dismissed=False).count(), 0
        )

    def test_marks_all_as_read(self):
        """When a user deletes all notifications, all of their notifications should also be marked as read (is_read=True) to ensure they don't show up as unread notifications."""
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_returns_success_json(self):
        """After deleting (dismissing) all, should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        """When a user deletes all notifications, it should not affect the notifications of other users."""
        make_notification(self.other, is_dismissed=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_dismissed=False).exists()
        )

    def test_already_dismissed_not_double_counted(self):
        """Notifications that are already dismissed (is_dismissed=True) should not cause any issues when marking all as read/dismissed again."""
        make_notification(self.user, is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_records_remain_in_db(self):
        """Delete all should soft-delete, not hard-delete."""
        make_notification(self.user)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(Notification.objects.filter(user=self.user).exists())

    def test_no_notifications_still_succeeds(self):
        """ If the user has no notifications, deleting all should still succeed and return a success JSON response."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})


class PollNotificationsTests(TestCase):
    """Tests for poll_notifications."""

    def setUp(self):
        """Create a user for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.url = reverse('poll_notifications')

    def test_login_required(self):
        """Polling notifications requires login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_returns_json(self):
        """When accessed by a logged-in user, the view should return a JSON response."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_returns_notifications_and_unread_count(self):
        """The JSON response should include a list of notifications and the count of unread notifications."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        data = response.json()
        self.assertIn('notifications', data)
        self.assertIn('unread_count', data)

    def test_returns_only_new_notifications_after_last_id(self):
        """When the last_id query parameter is provided, the view should return only notifications with an ID greater than last_id."""
        n1 = make_notification(self.user, title='Old')
        n2 = make_notification(self.user, title='New')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + f'?last_id={n1.pk}')
        ids = [n['id'] for n in response.json()['notifications']]
        self.assertNotIn(n1.pk, ids)
        self.assertIn(n2.pk, ids)

    def test_dismissed_notifications_excluded(self):
        """Notifications that are dismissed (is_dismissed=True) should not be included in the JSON response."""
        n = make_notification(self.user, title='Dismissed', is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        ids = [item['id'] for item in response.json()['notifications']]
        self.assertNotIn(n.pk, ids)

    def test_notification_fields_present(self):
        """Each notification in the JSON response should include the expected fields."""
        make_notification(self.user, title='My Notif', message='Hello')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        notif = response.json()['notifications'][0]
        for field in ['id', 'title', 'message', 'created_at', 'is_read']:
            self.assertIn(field, notif)

    def test_unread_count_correct(self):
        """The unread_count in the JSON response should reflect the number of unread and non-dismissed notifications for the user."""
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        self.assertEqual(response.json()['unread_count'], 2)

    def test_invalid_last_id_defaults_to_zero(self):
        """If the last_id query parameter is invalid (e.g. not a number), the view should default to treating it as 0 and return all notifications."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=notanumber')
        self.assertEqual(response.status_code, 200)

    def test_only_own_notifications_returned(self):
        """A user should only receive their own notifications in the JSON response, not those of other users."""
        other = User.objects.create_user(username='other2', password='pass')
        make_notification(other, title='Not Mine')
        n = make_notification(self.user, title='Mine')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        ids = [item['id'] for item in response.json()['notifications']]
        self.assertIn(n.pk, ids)
        self.assertEqual(len(ids), 1)

    def test_unread_count_excludes_dismissed(self):
        """Notifications that are dismissed (is_dismissed=True) should not be counted in the unread_count in the JSON response."""
        make_notification(self.user, is_read=False, is_dismissed=True)
        make_notification(self.user, is_read=False, is_dismissed=False)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        self.assertEqual(response.json()['unread_count'], 1)
