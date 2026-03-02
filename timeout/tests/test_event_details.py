# timeout/tests/test_event_details.py

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models import Event
from django.utils import timezone

User = get_user_model()

class EventDetailsViewTests(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')

        # Create an event for the test user
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
        """Logged-in user can access their event details"""
        self.client.login(username='testuser', password='password')
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/event_details.html')
        self.assertContains(response, self.event.title)
        self.assertContains(response, self.event.description)

    def test_event_details_view_not_creator(self):
        """Other users cannot access someone else's event"""
        self.client.login(username='otheruser', password='password')
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)  # should raise 404 for non-creator

    def test_event_details_view_redirects_if_not_logged_in(self):
        """Non-logged-in users are redirected to login"""
        url = reverse('event_details', args=[self.event.pk])
        response = self.client.get(url)
        self.assertRedirects(response, f'/accounts/login/?next={url}')