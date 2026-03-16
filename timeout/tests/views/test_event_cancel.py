from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from timeout.models.event import Event

User = get_user_model()


def make_event(creator, title='Test Event', event_type=None, duration_hours=1):
    """Helper to create a basic event."""
    now = timezone.now()
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=event_type or Event.EventType.OTHER,
        start_datetime=now + timezone.timedelta(hours=1),
        end_datetime=now + timezone.timedelta(hours=1 + duration_hours),
        status=Event.EventStatus.UPCOMING,
    )


class EventCancelViewTests(TestCase):
    """Tests for event_cancel view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='owner', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.event = make_event(self.user, title='My Meeting', event_type=Event.EventType.MEETING)
        self.url = reverse('event_cancel', kwargs={'pk': self.event.pk})

    # ── Authentication ────────────────────────────────────────

    def test_login_required_redirects_anonymous(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # ── Method ───────────────────────────────────────────────

    def test_get_request_not_allowed(self):
        self.client.login(username='owner', password='pass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # ── Ownership ─────────────────────────────────────────────

    def test_other_user_gets_404(self):
        self.client.login(username='other', password='pass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_event_returns_404(self):
        self.client.login(username='owner', password='pass123')
        url = reverse('event_cancel', kwargs={'pk': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    # ── Cancellation ──────────────────────────────────────────

    def test_event_status_set_to_cancelled(self):
        self.client.login(username='owner', password='pass123')
        self.client.post(self.url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.EventStatus.CANCELLED)

    def test_redirects_to_calendar_after_cancel(self):
        self.client.login(username='owner', password='pass123')
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('calendar'))

    def test_other_fields_not_changed(self):
        self.client.login(username='owner', password='pass123')
        original_title = self.event.title
        original_type = self.event.event_type
        self.client.post(self.url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, original_title)
        self.assertEqual(self.event.event_type, original_type)

    # ── Study session reschedule prompt ───────────────────────

    def test_cancel_study_session_adds_reschedule_prompt(self):
        event = make_event(
            self.user, title='Revision Session',
            event_type=Event.EventType.STUDY_SESSION,
            duration_hours=2,
        )
        url = reverse('event_cancel', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.post(url)
        prompts = self.client.session.get('reschedule_prompts', [])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]['id'], event.pk)
        self.assertEqual(prompts[0]['title'], 'Revision Session')
        self.assertEqual(prompts[0]['reason'], 'cancelled')

    def test_cancel_study_session_prompt_has_correct_duration(self):
        event = make_event(
            self.user, title='Long Session',
            event_type=Event.EventType.STUDY_SESSION,
            duration_hours=2,
        )
        url = reverse('event_cancel', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.post(url)
        prompts = self.client.session.get('reschedule_prompts', [])
        self.assertEqual(prompts[0]['duration_minutes'], 120)

    def test_cancel_non_study_session_no_reschedule_prompt(self):
        self.client.login(username='owner', password='pass123')
        self.client.post(self.url)
        prompts = self.client.session.get('reschedule_prompts', [])
        self.assertEqual(len(prompts), 0)

    def test_cancel_multiple_study_sessions_appends_prompts(self):
        event1 = make_event(self.user, title='Session 1', event_type=Event.EventType.STUDY_SESSION)
        event2 = make_event(self.user, title='Session 2', event_type=Event.EventType.STUDY_SESSION)
        self.client.login(username='owner', password='pass123')
        self.client.post(reverse('event_cancel', kwargs={'pk': event1.pk}))
        self.client.post(reverse('event_cancel', kwargs={'pk': event2.pk}))
        prompts = self.client.session.get('reschedule_prompts', [])
        self.assertEqual(len(prompts), 2)
        titles = [p['title'] for p in prompts]
        self.assertIn('Session 1', titles)
        self.assertIn('Session 2', titles)

    # ── Event types ───────────────────────────────────────────

    def test_cancel_deadline_event(self):
        event = make_event(self.user, title='Assignment', event_type=Event.EventType.DEADLINE)
        url = reverse('event_cancel', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.post(url)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.EventStatus.CANCELLED)

    def test_cancel_exam_event(self):
        event = make_event(self.user, title='Finals', event_type=Event.EventType.EXAM)
        url = reverse('event_cancel', kwargs={'pk': event.pk})
        self.client.login(username='owner', password='pass123')
        self.client.post(url)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.EventStatus.CANCELLED)

    def test_cancel_already_cancelled_event(self):
        self.event.status = Event.EventStatus.CANCELLED
        self.event.save()
        self.client.login(username='owner', password='pass123')
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('calendar'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.EventStatus.CANCELLED)