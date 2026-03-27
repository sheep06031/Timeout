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

    def test_empty_notifications(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['notifications'])), 0)

    def test_ajax_returns_json(self):
        make_notification(self.user, title='Ajax notif')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('notifications', data)
        self.assertIn('has_next', data)
        self.assertIn('next_page', data)

    def test_ajax_notification_fields(self):
        make_notification(self.user, title='Ajax notif', message='Hello')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        notif = response.json()['notifications'][0]
        for field in ['id', 'title', 'message', 'type', 'is_read', 'created_at']:
            self.assertIn(field, notif)

    def test_ajax_has_next_false_when_few_notifications(self):
        make_notification(self.user, title='Only one')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(response.json()['has_next'])

    def test_ajax_has_next_true_when_many_notifications(self):
        for i in range(20):
            make_notification(self.user, title=f'N{i}')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(response.json()['has_next'])

    def test_ajax_next_page_is_none_when_no_next(self):
        make_notification(self.user, title='Only one')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsNone(response.json()['next_page'])

    def test_ajax_next_page_number_when_has_next(self):
        for i in range(20):
            make_notification(self.user, title=f'N{i}')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['next_page'], 2)


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
        self.client.post(self.url)
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


class MarkNotificationUnreadTests(TestCase):
    """Tests for mark_notification_unread."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.notif = make_notification(self.user, title='Read', is_read=True)
        self.url = reverse('mark_notification_unread', kwargs={'notification_id': self.notif.pk})

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_notification_as_unread(self):
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_other_user_cannot_mark_unread(self):
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        self.client.login(username='user', password='pass123')
        url = reverse('mark_notification_unread', kwargs={'notification_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class MarkAllNotificationsReadTests(TestCase):
    """Tests for mark_all_notifications_read."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('mark_all_notifications_read')

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_all_unread_as_read(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        make_notification(self.other, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=False).exists()
        )

    def test_does_not_affect_dismissed_notifications(self):
        n = make_notification(self.user, is_read=False, is_dismissed=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_no_notifications_still_succeeds(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})


class MarkAllNotificationsUnreadTests(TestCase):
    """Tests for mark_all_notifications_unread."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('mark_all_notifications_unread')

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_marks_all_read_as_unread(self):
        make_notification(self.user, is_read=True)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=True).count(), 0
        )

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        make_notification(self.other, is_read=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=True).exists()
        )

    def test_does_not_affect_dismissed_notifications(self):
        n = make_notification(self.user, is_read=True, is_dismissed=True)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_no_notifications_still_succeeds(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})


class DeleteNotificationTests(TestCase):
    """Tests for delete_notification (soft delete via is_dismissed=True)."""

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


class DeleteAllNotificationsTests(TestCase):
    """Tests for delete_all_notifications."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.url = reverse('delete_all_notifications')

    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_dismisses_all_notifications(self):
        make_notification(self.user)
        make_notification(self.user)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_dismissed=False).count(), 0
        )

    def test_marks_all_as_read(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_returns_success_json(self):
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})

    def test_does_not_affect_other_users(self):
        make_notification(self.other, is_dismissed=False)
        self.client.login(username='user', password='pass123')
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_dismissed=False).exists()
        )

    def test_already_dismissed_not_double_counted(self):
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
        self.client.login(username='user', password='pass123')
        response = self.client.post(self.url)
        self.assertJSONEqual(response.content, {'success': True})


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
        ids = [n['id'] for n in response.json()['notifications']]
        self.assertNotIn(n1.pk, ids)
        self.assertIn(n2.pk, ids)

    def test_dismissed_notifications_excluded(self):
        n = make_notification(self.user, title='Dismissed', is_dismissed=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        ids = [item['id'] for item in response.json()['notifications']]
        self.assertNotIn(n.pk, ids)

    def test_notification_fields_present(self):
        make_notification(self.user, title='My Notif', message='Hello')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        notif = response.json()['notifications'][0]
        for field in ['id', 'title', 'message', 'created_at', 'is_read']:
            self.assertIn(field, notif)

    def test_unread_count_correct(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        self.assertEqual(response.json()['unread_count'], 2)

    def test_invalid_last_id_defaults_to_zero(self):
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=notanumber')
        self.assertEqual(response.status_code, 200)

    def test_only_own_notifications_returned(self):
        other = User.objects.create_user(username='other2', password='pass')
        make_notification(other, title='Not Mine')
        n = make_notification(self.user, title='Mine')
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        ids = [item['id'] for item in response.json()['notifications']]
        self.assertIn(n.pk, ids)
        self.assertEqual(len(ids), 1)

    def test_unread_count_excludes_dismissed(self):
        make_notification(self.user, is_read=False, is_dismissed=True)
        make_notification(self.user, is_read=False, is_dismissed=False)
        self.client.login(username='user', password='pass123')
        response = self.client.get(self.url + '?last_id=0')
        self.assertEqual(response.json()['unread_count'], 1)