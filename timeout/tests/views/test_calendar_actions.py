"""
Tests for the calendar-related views in the timeout app, including event creation, applying session schedules, and subscribing to events.
Includes tests for:
- Event creation: normal events, recurring events, all-day events, validation errors, optional fields, authentication and method guards
- Applying session schedules: successful updates, invalid JSON, non-existent events, wrong event types, missing keys, empty sessions list, authentication and method guards
- Subscribing to events: successful subscription, owner cannot subscribe, already subscribed, private event 404, nonexistent event 404, authentication and method guards
"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from timeout.models import Event

User = get_user_model()


class EventCreateTests(TestCase):
    """Tests for the event_create view."""

    def setUp(self):
        """Create a user, log in, and store the event_create URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="creator", password="pass1234")
        self.client.login(username="creator", password="pass1234")
        self.url = reverse("event_create")

    def test_create_normal_event(self):
        """Creating a normal event with all required fields should succeed and redirect to the calendar."""
        resp = self.client.post(self.url, {
            "title": "Team Meeting",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T10:00",
            "visibility": "public",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertTrue(Event.objects.filter(title="Team Meeting").exists())

    def test_create_event_with_recurrence(self):
        """Creating an event with a valid recurrence pattern should save the recurrence field correctly."""
        resp = self.client.post(self.url, {
            "title": "Daily Standup",
            "event_type": "other",
            "start_datetime": "2025-04-10T09:00",
            "end_datetime": "2025-04-10T09:15",
            "recurrence": "daily",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        self.assertEqual(Event.objects.get(title="Daily Standup").recurrence, "daily")

    def test_all_day_event_forces_midnight_times(self):
        """Creating an all-day event should set the start time to 00:00 and end time to 23:59 regardless of input."""
        resp = self.client.post(self.url, {
            "title": "Holiday",
            "event_type": "other",
            "start_datetime": "2025-04-10T14:30",
            "is_all_day": "on",
        })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)
        event = Event.objects.get(title="Holiday")
        self.assertEqual(event.start_datetime.hour, 0)
        self.assertEqual(event.start_datetime.minute, 0)
        self.assertEqual(event.end_datetime.hour, 23)
        self.assertEqual(event.end_datetime.minute, 59)

    def test_all_day_event_missing_start_datetime_shows_error(self):
        """Creating an all-day event without a start datetime should fail validation and not create the event."""
        self.client.post(self.url, {"title": "Bad All-Day", "event_type": "other", "is_all_day": "on"})
        self.assertFalse(Event.objects.filter(title="Bad All-Day").exists())

    def test_missing_datetimes_non_all_day(self):
        """Creating a non-all-day event without start or end datetimes should fail validation and not create the event."""
        self.client.post(self.url, {"title": "No Start", "event_type": "other", "end_datetime": "2025-04-10T10:00"})
        self.assertFalse(Event.objects.filter(title="No Start").exists())
        self.client.post(self.url, {"title": "No End", "event_type": "other", "start_datetime": "2025-04-10T09:00"})
        self.assertFalse(Event.objects.filter(title="No End").exists())

    def test_validation_error_shows_message(self):
        """If the Event model raises a ValidationError during creation, the view should catch it and display an error message."""
        with patch.object(Event, "full_clean", side_effect=__import__("django.core.exceptions", fromlist=["ValidationError"]).ValidationError("bad")):
            resp = self.client.post(self.url, {
                "title": "Invalid",
                "event_type": "other",
                "start_datetime": "2025-04-10T09:00",
                "end_datetime": "2025-04-10T10:00",
            })
        self.assertRedirects(resp, reverse("calendar"), fetch_redirect_response=False)

    def test_defaults_for_optional_fields(self):
        """Creating an event without optional fields should set those fields to their default values."""
        self.client.post(self.url, {"title": "Minimal", "start_datetime": "2025-04-10T09:00", "end_datetime": "2025-04-10T10:00"})
        event = Event.objects.get(title="Minimal")
        self.assertEqual(event.recurrence, "none")
        self.assertEqual(event.event_type, "other")
        self.assertEqual(event.location, "")
        self.assertEqual(event.description, "")

    def test_unauthenticated_post_redirects(self):
        """Unauthenticated users should be redirected to the login page when trying to create an event."""
        self.client.logout()
        resp = self.client.post(self.url, {"title": "nope"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_get_request_not_allowed(self):
        """The event_create view should only allow POST requests; GET requests should return a 405 Method Not Allowed."""
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ApplySessionScheduleTests(TestCase):
    """Tests for the apply_session_schedule view."""

    def setUp(self):
        """Create a user, log in, and store the apply_session_schedule URL."""
        self.client = Client()
        self.user = User.objects.create_user(username="scheduser", password="pass1234")
        self.client.login(username="scheduser", password="pass1234")
        self.url = reverse("apply_session_schedule")

    def _create_session(self, title="Study", start_offset=timedelta(days=1), duration_hours=2):
        """Helper to create a study session event for testing."""
        now = timezone.now()
        return Event.objects.create(
            creator=self.user,
            title=title,
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=now + start_offset,
            end_datetime=now + start_offset + timedelta(hours=duration_hours),
        )

    def test_update_sessions_success(self):
        """Posting valid session data should update the corresponding events and return success=True with the count of updated sessions."""
        session = self._create_session()
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": session.pk, "start": "2025-05-01T10:00", "end": "2025-05-01T12:00"}])
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)

    def test_invalid_json_returns_400(self):
        """Posting invalid JSON should return a 400 Bad Request with success=False in the response."""
        resp = self.client.post(self.url, {"sessions": "not-valid-json"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    def test_nonexistent_event_skipped(self):
        """If the posted session data references an event ID that doesn't exist, it should be skipped and not cause an error."""
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": 99999, "start": "2025-05-01T10:00", "end": "2025-05-01T12:00"}])
        })
        self.assertEqual(resp.json()["count"], 0)

    def test_wrong_event_type_skipped(self):
        """If the posted session data references an event that exists but is not a study session, it should be skipped and not updated."""
        event = Event.objects.create(
            creator=self.user,
            title="Not a session",
            event_type=Event.EventType.DEADLINE,
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.post(self.url, {
            "sessions": json.dumps([{"id": event.pk, "start": "2025-05-01T10:00", "end": "2025-05-01T12:00"}])
        })
        self.assertEqual(resp.json()["count"], 0)

    def test_missing_key_skipped(self):
        """If the posted session data is missing required keys (like 'start' or 'end'), it should be skipped and not cause an error."""
        session = self._create_session()
        resp = self.client.post(self.url, {"sessions": json.dumps([{"id": session.pk}])})
        self.assertEqual(resp.json()["count"], 0)

    def test_empty_sessions_list(self):
        """Posting an empty list of sessions should succeed with count=0 and not cause any errors."""
        resp = self.client.post(self.url, {"sessions": json.dumps([])})
        self.assertEqual(resp.json()["count"], 0)

    def test_auth_and_method_guards(self):
        """Unauthenticated users should be redirected to login, and GET requests should return 405 Method Not Allowed."""
        self.client.logout()
        resp = self.client.post(self.url, {"sessions": "[]"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)
        self.client.login(username="scheduser", password="pass1234")
        self.assertEqual(self.client.get(self.url).status_code, 405)


class SubscribeEventTests(TestCase):
    """Tests for the subscribe_event view."""

    def setUp(self):
        """Create an owner and a subscriber user, log in as subscriber, and create a public event."""
        self.client = Client()
        self.owner = User.objects.create_user(username="owner", password="pass1234")
        self.subscriber = User.objects.create_user(username="subscriber", password="pass1234")
        self.client.login(username="subscriber", password="pass1234")
        now = timezone.now()
        self.public_event = Event.objects.create(
            creator=self.owner,
            title="Public Lecture",
            event_type=Event.EventType.CLASS,
            start_datetime=now + timedelta(days=1),
            end_datetime=now + timedelta(days=1, hours=2),
            visibility=Event.Visibility.PUBLIC,
        )

    def _url(self, pk):
        """Helper to construct the subscribe_event URL for a given event ID."""
        return reverse("subscribe_event", kwargs={"pk": pk})

    def test_subscribe_success(self):
        """A user should be able to subscribe to a public event they don't own, resulting in a new event created for the subscriber with the same details."""
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertTrue(Event.objects.filter(creator=self.subscriber, title="Public Lecture").exists())

    def test_owner_cannot_subscribe(self):
        """Event creators should not be able to subscribe to their own events; the view should return a 400 Bad Request in this case."""
        self.client.login(username="owner", password="pass1234")
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["success"])

    def test_already_subscribed(self):
        """If a user tries to subscribe to an event they are already subscribed to, the view should return a 400 Bad Request with an appropriate error message."""
        self.client.post(self._url(self.public_event.pk))
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Already", resp.json()["error"])

    def test_private_event_404(self):
        """Users should not be able to subscribe to private events they don't own; the view should return a 404 Not Found in this case to avoid leaking the existence of the event."""
        private_event = Event.objects.create(
            creator=self.owner,
            title="Private Meeting",
            event_type=Event.EventType.MEETING,
            start_datetime=timezone.now() + timedelta(days=1),
            end_datetime=timezone.now() + timedelta(days=1, hours=1),
            visibility=Event.Visibility.PRIVATE,
        )
        self.assertEqual(self.client.post(self._url(private_event.pk)).status_code, 404)

    def test_nonexistent_event_404(self):
        """Trying to subscribe to an event that doesn't exist should return a 404 Not Found error."""
        self.assertEqual(self.client.post(self._url(99999)).status_code, 404)

    def test_auth_and_method_guards(self):
        """Unauthenticated users should be redirected to login, and GET requests should return 405 Method Not Allowed."""
        self.client.logout()
        resp = self.client.post(self._url(self.public_event.pk))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)
        self.client.login(username="subscriber", password="pass1234")
        self.assertEqual(self.client.get(self._url(self.public_event.pk)).status_code, 405)
