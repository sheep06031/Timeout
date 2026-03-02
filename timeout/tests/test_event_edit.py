# timeout/tests/test_views.py

from django.test import TestCase
from django.urls import reverse
from timeout.models import Event
from django.utils import timezone

class EventEditViewTests(TestCase):
    def setUp(self):
        # Create a test event
        self.event = Event.objects.create(
            title="Test Event",
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=1),
            description="Initial description",
            location="Test Location",
            event_type="meeting",
            allow_conflict=False
        )

    def test_get_event_edit_page(self):
        """GET request returns 200 and uses correct template"""
        url = reverse("event_edit", args=[self.event.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/event_form.html")
        self.assertContains(response, "Edit Event")
        self.assertContains(response, self.event.title)

    def test_post_event_edit_updates_event(self):
        """POST request updates the event and redirects"""
        url = reverse("event_edit", args=[self.event.pk])
        new_data = {
            "title": "Updated Event",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "end_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "description": "Updated description",
            "location": "Updated Location",
            "event_type": "deadline",
            "allow_conflict": "on",
        }
        response = self.client.post(url, new_data)

        # Should redirect to event detail
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Updated Event")
        self.assertEqual(self.event.description, "Updated description")
        self.assertEqual(self.event.location, "Updated Location")
        self.assertEqual(self.event.event_type, "deadline")
        self.assertTrue(self.event.allow_conflict)

    def test_post_event_edit_without_allow_conflict(self):
        """allow_conflict checkbox not checked should be False"""
        url = reverse("event_edit", args=[self.event.pk])
        new_data = {
            "title": "No Conflict Event",
            "start_datetime": timezone.now().isoformat(),
            "end_datetime": (timezone.now() + timezone.timedelta(hours=1)).isoformat(),
            "description": "No conflict",
            "location": "Nowhere",
            "event_type": "class",
        }
        response = self.client.post(url, new_data)
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertFalse(self.event.allow_conflict)
        self.assertEqual(self.event.title, "No Conflict Event")