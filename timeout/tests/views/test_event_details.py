"""
Tests for the event_details view in the timeout app, which displays the details of a specific event to its creator.
"""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models import Event
from django.utils import timezone

User = get_user_model()


class EventDetailsViewTests(TestCase):
    """Tests for the event_details view."""

    def setUp(self):
        """Create two users and an event owned by the first user."""
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')

        self.event = Event.objects.create(
            title="Test Event",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            description="A test event",
            location="Test Location",
            event_type="meeting",
            creator=self.user
        )

    def test_event_details_view_logged_in(self):
        """The event creator should see the event details page with a 200 status."""
        self.client.login(username='testuser', password='password')
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/event_details.html')
        self.assertContains(response, self.event.title)

    def test_event_details_view_not_creator(self):
        """A user who is not the event creator should receive a 404."""
        self.client.login(username='otheruser', password='password')
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_event_details_view_redirects_if_not_logged_in(self):
        """Unauthenticated users should be redirected to the login page."""
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
