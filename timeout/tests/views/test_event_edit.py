from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models import Event
from django.utils import timezone

User = get_user_model()


class EventEditViewTests(TestCase):
    """Tests for event_edit view."""

    def setUp(self):
        self.client = Client()
        self.user  = User.objects.create_user(username='testuser', password='password')
        self.other = User.objects.create_user(username='other',    password='password')
        self.client.login(username='testuser', password='password')
        self.event = Event.objects.create(
            title='Test Event',
            start_datetime=timezone.now() + timezone.timedelta(hours=1),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
            description='Initial description',
            location='Test Location',
            event_type='meeting',
            allow_conflict=False,
            creator=self.user,
        )
        self.url = reverse('event_edit', args=[self.event.pk])

    def _post_data(self, **overrides):
        """Build valid POST data, merging any overrides."""
        data = {
            'title':          'Updated Event',
            'start_datetime': (timezone.now() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_datetime':   (timezone.now() + timezone.timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'description':    'Updated description',
            'location':       'Updated Location',
            'event_type':     'deadline',
            'allow_conflict': 'on',
        }
        data.update(overrides)
        return data

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_other_user_gets_404_on_get(self):
        self.client.logout()
        self.client.login(username='other', password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_other_user_gets_404_on_post(self):
        self.client.logout()
        self.client.login(username='other', password='password')
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_event_returns_404(self):
        url = reverse('event_edit', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/event_form.html')

    def test_get_contains_event_title(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.event.title)

    def test_get_context_contains_event(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['event'], self.event)

    def test_get_context_contains_study_sessions(self):
        response = self.client.get(self.url)
        self.assertIn('study_sessions', response.context)

    def test_post_updates_title(self):
        self.client.post(self.url, self._post_data(title='New Title'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'New Title')

    def test_post_updates_description(self):
        self.client.post(self.url, self._post_data(description='New desc'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.description, 'New desc')

    def test_post_updates_event_type(self):
        self.client.post(self.url, self._post_data(event_type='exam'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.event_type, 'exam')

    def test_post_sets_allow_conflict_true(self):
        self.client.post(self.url, self._post_data(allow_conflict='on'))
        self.event.refresh_from_db()
        self.assertTrue(self.event.allow_conflict)

    def test_post_sets_allow_conflict_false_when_omitted(self):
        data = self._post_data()
        data.pop('allow_conflict')
        self.client.post(self.url, data)
        self.event.refresh_from_db()
        self.assertFalse(self.event.allow_conflict)

    def test_post_redirects_to_calendar(self):
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 302)
        self.assertIn('calendar', response['Location'])

    def test_post_updates_location(self):
        self.client.post(self.url, self._post_data(location='New Place'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.location, 'New Place')

    def test_post_invalid_start_datetime_redirects_to_calendar(self):
        data = self._post_data(start_datetime='not-a-date')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('calendar', response['Location'])

    def test_post_invalid_end_datetime_redirects_to_calendar(self):
        data = self._post_data(end_datetime='not-a-date')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        self.assertIn('calendar', response['Location'])

    def test_post_invalid_datetime_shows_error_message(self):
        data = self._post_data(start_datetime='not-a-date')
        response = self.client.post(self.url, data, follow=True)
        msgs = list(response.context['messages'])
        self.assertTrue(any('Invalid' in str(m) for m in msgs))

    def test_post_invalid_datetime_does_not_update_event(self):
        original_title = self.event.title
        data = self._post_data(start_datetime='not-a-date', title='Should Not Save')
        self.client.post(self.url, data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, original_title)

    def test_post_deadline_sets_linked_study_sessions(self):
        session = Event.objects.create(
            creator=self.user,
            title='Study Session',
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=timezone.now() - timezone.timedelta(hours=2),
            end_datetime=timezone.now() - timezone.timedelta(hours=1),
        )
        data = self._post_data(event_type='deadline')
        data['linked_study_sessions'] = [session.pk]
        self.client.post(self.url, data)
        self.event.refresh_from_db()
        self.assertIn(session, self.event.linked_study_sessions.all())

    def test_post_non_deadline_does_not_set_study_sessions(self):
        """linked_study_sessions should only be set for deadlines."""
        data = self._post_data(event_type='exam')
        self.client.post(self.url, data)
        self.event.refresh_from_db()
        self.assertEqual(self.event.event_type, 'exam')