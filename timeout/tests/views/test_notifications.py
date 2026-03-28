"""
test_notifications.py - Defines tests for the notifications view and related actions (marking as read/unread, marking all as read/unread),
covering authentication requirements, correct filtering of notifications, AJAX response structure, and user isolation.
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


class NotificationsViewTests(TestCase):
    """Tests for notifications_view."""

    def setUp(self):
        """Create two users for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('notifications')

    def test_login_required_redirects_anonymous(self):
        """Anonymous users should be redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_renders_notifications_page(self):
        """A logged-in user should see the notifications page with a 200 status."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/notifications.html')

    def test_shows_only_own_notifications(self):
        """A user should only see their own notifications, not those of other users."""
        make_notification(self.user, title='Mine')
        make_notification(self.other, title='Not Mine')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Mine')

    def test_dismissed_notifications_not_shown(self):
        """Notifications that are dismissed (is_dismissed=True) should not be shown in the notifications list."""
        make_notification(self.user, title='Visible')
        make_notification(self.user, title='Dismissed', is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Visible')

    def test_unread_count_in_context(self):
        """The context should include the count of unread notifications for the user."""
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['unread_count'], 2)

    def test_filter_unread_only(self):
        """When the filter=unread query parameter is used, only unread notifications should be shown."""
        make_notification(self.user, title='Unread', is_read=False)
        make_notification(self.user, title='Read', is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?filter=unread')
        notifications = list(response.context['notifications'])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Unread')

    def test_filter_param_in_context(self):
        """The current filter parameter should be included in the context for use in the template."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?filter=unread')
        self.assertEqual(response.context['current_filter'], 'unread')

    def test_no_filter_shows_all_non_dismissed(self):
        """When no filter query parameter is used, all non-dismissed notifications should be shown regardless of read status."""
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context['notifications'])), 2)

    def test_empty_notifications(self):
        """If the user has no notifications, the notifications list in the context should be empty."""
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['notifications'])), 0)

    def test_ajax_returns_json(self):
        """When accessed with an AJAX request, the view should return a JSON response containing notifications data."""
        make_notification(self.user, title='Ajax notif')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('notifications', data)
        self.assertIn('has_next', data)
        self.assertIn('next_page', data)

    def test_ajax_notification_fields(self):
        """The JSON response for AJAX requests should include the expected fields for each notification."""
        make_notification(self.user, title='Ajax notif', message='Hello')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        notif = response.json()['notifications'][0]
        for field in ['id', 'title', 'message', 'type', 'is_read', 'created_at']:
            self.assertIn(field, notif)

    def test_ajax_has_next_false_when_few_notifications(self):
        """If there are fewer notifications than the pagination limit, has_next should be False."""
        make_notification(self.user, title='Only one')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(response.json()['has_next'])

    def test_ajax_has_next_true_when_many_notifications(self):
        """If there are more notifications than the pagination limit, has_next should be True."""
        for i in range(20):
            make_notification(self.user, title=f'N{i}')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['has_next'])

    def test_ajax_next_page_is_none_when_no_next(self):
        """If there are no more notifications to load, next_page should be None."""
        make_notification(self.user, title='Only one')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsNone(response.json()['next_page'])

    def test_ajax_next_page_number_when_has_next(self):
        """If there are more notifications to load, next_page should be the number of the next page (e.g. 2)."""
        for i in range(20):
            make_notification(self.user, title=f'N{i}')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['next_page'], 2)


class MarkNotificationReadTests(TestCase):
    """Tests for mark_notification_read."""

    def setUp(self):
        """Create a user and a notification for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='Unread', is_read=False)
        self.url = reverse('mark_notification_read', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        """Marking a notification as read requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_notification_as_read(self):
        """A user should be able to mark their own notification as read, which sets is_read=True."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_returns_success_json(self):
        """After marking as read, should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_mark_read(self):
        """A user should not be able to mark another user's notification as read (should return 404)."""
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        """If the notification ID does not exist, should return a 404 error."""
        self.client.login(username='user', password='pass123')
        url = reverse('mark_notification_read', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_already_read_notification_stays_read(self):
        """If the notification is already marked as read, marking it as read again should have no effect (should still be read)."""
        self.notif.is_read = True
        self.notif.save()
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)


class MarkNotificationUnreadTests(TestCase):
    """Tests for mark_notification_unread."""

    def setUp(self):
        """Create a user and a notification for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='Read', is_read=True)
        self.url = reverse('mark_notification_unread', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        """Marking a notification as unread requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_notification_as_unread(self):
        """A user should be able to mark their own notification as unread, which sets is_read=False."""
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_returns_success_json(self):
        """After marking as unread, should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_mark_unread(self):
        """A user should not be able to mark another user's notification as unread (should return 404)."""
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        """If the notification ID does not exist, should return a 404 error."""
        self.client.login(username='user', password='pass123')
        url = reverse('mark_notification_unread', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class MarkAllNotificationsReadTests(TestCase):
    """Tests for mark_all_notifications_read."""

    def setUp(self):
        """Create a user for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('mark_all_notifications_read')

    def test_login_required(self):
        """Marking all notifications as read requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_all_unread_as_read(self):
        """When a user marks all notifications as read, all of their notifications with is_read=False should be updated to is_read=True."""
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_returns_success_json(self):
        """After marking all as read, should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        """When a user marks all notifications as read, it should not affect the notifications of other users."""
        make_notification(self.other, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=False).exists()
        )

    def test_does_not_affect_dismissed_notifications(self):
        """Notifications that are dismissed (is_dismissed=True) should not be marked as read when marking all as read."""
        n = make_notification(self.user, is_read=False, is_dismissed=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_no_notifications_still_succeeds(self):
        """If the user has no notifications, marking all as read should still succeed and return a success JSON response."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})


class MarkAllNotificationsUnreadTests(TestCase):
    """Tests for mark_all_notifications_unread."""

    def setUp(self):
        """Create a user for testing."""
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('mark_all_notifications_unread')

    def test_login_required(self):
        """Marking all notifications as unread requires login."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_all_read_as_unread(self):
        """When a user marks all notifications as unread, all of their notifications with is_read=True should be updated to is_read=False."""
        make_notification(self.user, is_read=True)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=True).count(), 0
        )

    def test_returns_success_json(self):
        """After marking all as unread, should return a JSON response indicating success."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        """When a user marks all notifications as unread, it should not affect the notifications of other users."""
        make_notification(self.other, is_read=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=True).exists()
        )

    def test_does_not_affect_dismissed_notifications(self):
        """Notifications that are dismissed (is_dismissed=True) should not be marked as unread when marking all as unread."""
        n = make_notification(self.user, is_read=True, is_dismissed=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_no_notifications_still_succeeds(self):
        """If the user has no notifications, marking all as unread should still succeed and return a success JSON response."""
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})