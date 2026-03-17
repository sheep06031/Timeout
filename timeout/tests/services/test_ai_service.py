"""
Tests for AIService.get_dashboard_briefing and _call_openai_for_briefing.

Covers: unauthenticated user, cache hit, no API key, successful OpenAI call,
OpenAI exception handling, stat gathering logic, and most_productive_day branch.

Place in: timeout/tests/services/test_ai_service.py
"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from timeout.models import Event
from timeout.services.ai_service import AIService, _call_openai_for_briefing

User = get_user_model()

MOCK_NOW = timezone.make_aware(datetime(2025, 4, 10, 12, 0, 0))


class AIServiceGetBriefingTests(TestCase):
    """Tests for AIService.get_dashboard_briefing."""

    def setUp(self):
        self.user = User.objects.create_user(username="aiuser", password="pass1234")
        cache.clear()

    def tearDown(self):
        cache.clear()

    # -- Unauthenticated user returns None ---------------------------
    def test_unauthenticated_returns_none(self):
        result = AIService.get_dashboard_briefing(AnonymousUser())
        self.assertIsNone(result)

    # -- Cache hit returns cached value without calling OpenAI -------
    @override_settings(OPENAI_API_KEY="test-key")
    def test_cache_hit_returns_cached(self):
        cache.set(f'ai_briefing_{self.user.id}', "Cached briefing", 300)
        result = AIService.get_dashboard_briefing(self.user)
        self.assertEqual(result, "Cached briefing")

    # -- Successful OpenAI call --------------------------------------
    @patch("timeout.services.ai_service.timezone.now", return_value=MOCK_NOW)
    @patch("timeout.services.ai_service._call_openai_for_briefing")
    def test_successful_briefing(self, mock_openai, mock_now):
        mock_openai.return_value = "Great week! You studied 5 hours."
        result = AIService.get_dashboard_briefing(self.user)
        self.assertEqual(result, "Great week! You studied 5 hours.")
        mock_openai.assert_called_once()
        cached = cache.get(f'ai_briefing_{self.user.id}')
        self.assertEqual(cached, "Great week! You studied 5 hours.")

    # -- OpenAI returns None → method returns None -------------------
    @patch("timeout.services.ai_service.timezone.now", return_value=MOCK_NOW)
    @patch("timeout.services.ai_service._call_openai_for_briefing", return_value=None)
    def test_openai_returns_none(self, mock_openai, mock_now):
        result = AIService.get_dashboard_briefing(self.user)
        self.assertIsNone(result)

    # -- Stats gathering with study events ---------------------------
    @patch("timeout.services.ai_service._call_openai_for_briefing")
    def test_stats_include_study_hours(self, mock_openai):
        mock_openai.return_value = "You studied hard!"
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title="Study",
            event_type=Event.EventType.STUDY_SESSION,
            start_datetime=now - timedelta(days=1),
            end_datetime=now - timedelta(days=1) + timedelta(hours=3),
        )
        result = AIService.get_dashboard_briefing(self.user)
        self.assertIsNotNone(result)
        call_args = mock_openai.call_args[0][0]
        self.assertGreater(call_args['total_study_hours'], 0)

    # -- Stats with missed deadlines and completed events ------------
    @patch("timeout.services.ai_service._call_openai_for_briefing")
    def test_stats_count_missed_deadlines_and_completed(self, mock_openai):
        mock_openai.return_value = "Keep going!"
        now = timezone.now()
        Event.objects.create(
            creator=self.user, title="Missed DL",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(hours=1),
            is_completed=False,
        )
        Event.objects.create(
            creator=self.user, title="Completed",
            event_type=Event.EventType.DEADLINE,
            start_datetime=now - timedelta(days=1),
            end_datetime=now + timedelta(days=1),
            is_completed=True,
        )
        AIService.get_dashboard_briefing(self.user)
        call_args = mock_openai.call_args[0][0]
        self.assertGreaterEqual(call_args['missed_deadlines'], 1)
        self.assertGreaterEqual(call_args['completed_tasks'], 1)

    # -- No completed events → most_productive_day is 'None yet' -----
    @patch("timeout.services.ai_service._call_openai_for_briefing")
    def test_no_completed_events_productive_day_none(self, mock_openai):
        mock_openai.return_value = "Keep it up!"
        AIService.get_dashboard_briefing(self.user)
        call_args = mock_openai.call_args[0][0]
        self.assertEqual(call_args['most_productive_day'], 'None yet')

    # -- Has completed events → most_productive_day is a day name ----
    @patch("timeout.services.ai_service._call_openai_for_briefing")
    def test_most_productive_day_with_completed_events(self, mock_openai):
        mock_openai.return_value = "Nice work!"
        now = timezone.now()
        for i in range(2):
            Event.objects.create(
                creator=self.user, title=f"Task {i}",
                event_type=Event.EventType.DEADLINE,
                start_datetime=now - timedelta(days=1, hours=i),
                end_datetime=now - timedelta(days=1, hours=i) + timedelta(hours=1),
                is_completed=True,
            )
        AIService.get_dashboard_briefing(self.user)
        call_args = mock_openai.call_args[0][0]
        self.assertNotEqual(call_args['most_productive_day'], 'None yet')
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        self.assertIn(call_args['most_productive_day'], valid_days)


class CallOpenAIForBriefingTests(TestCase):
    """Tests for the _call_openai_for_briefing helper."""

    # -- No API key returns None ------------------------------------
    @override_settings(OPENAI_API_KEY=None)
    def test_no_api_key_returns_none(self):
        result = _call_openai_for_briefing({"total_study_hours": 5})
        self.assertIsNone(result)

    @override_settings(OPENAI_API_KEY="")
    def test_empty_api_key_returns_none(self):
        result = _call_openai_for_briefing({"total_study_hours": 5})
        self.assertIsNone(result)

    # -- Successful OpenAI call -------------------------------------
    @override_settings(OPENAI_API_KEY="test-key-123")
    @patch("openai.OpenAI")
    def test_successful_call(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "  Great week!  "
        mock_client.chat.completions.create.return_value = mock_response

        result = _call_openai_for_briefing({"total_study_hours": 10})
        self.assertEqual(result, "Great week!")

    # -- OpenAI raises exception → returns None ---------------------
    @override_settings(OPENAI_API_KEY="test-key-123")
    @patch("openai.OpenAI")
    def test_exception_returns_none(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")

        result = _call_openai_for_briefing({"total_study_hours": 5})
        self.assertIsNone(result)