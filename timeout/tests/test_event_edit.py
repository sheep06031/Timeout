from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from timeout.models import Event
from django.utils import timezone

User = get_user_model()


class EventEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

        self.event = Event.objects.create(
            title="Test Event",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            description="Initial description",
            location="Test Location",
            event_type="meeting",
            allow_conflict=False,
            creator=self.user
        )

    def test_get_event_edit_page(self):
        url = reverse("event_edit", args=[self.event.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/event_form.html")
        self.assertContains(response, self.event.title)

    def test_post_event_edit_updates_event(self):
        url = reverse("event_edit", args=[self.event.pk])
        new_data = {
            "title": "Updated Event",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            "end_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            "description": "Updated description",
            "location": "Updated Location",
            "event_type": "deadline",
            "allow_conflict": "on",
        }
        response = self.client.post(url, new_data)
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Updated Event")
        self.assertEqual(self.event.description, "Updated description")
        self.assertTrue(self.event.allow_conflict)

    def test_post_event_edit_without_allow_conflict(self):
        url = reverse("event_edit", args=[self.event.pk])
        new_data = {
            "title": "No Conflict Event",
            "start_datetime": timezone.now().strftime('%Y-%m-%dT%H:%M'),
            "end_datetime": (timezone.now() + timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            "description": "No conflict",
            "location": "Nowhere",
            "event_type": "class",
        }
        response = self.client.post(url, new_data)
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertFalse(self.event.allow_conflict)
