from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from timeout.views.ai_workload import get_ai_workload_warning

User = get_user_model()


class AiWorkloadHelperTests(TestCase):

    def setUp(self):
        cache.clear() 
        self.user = User.objects.create_user(username="testuser", password="pass123")
        now = datetime.now()
        self.events = [
            MagicMock(title="Meeting", start_datetime=now, end_datetime=now + timedelta(hours=1)),
            MagicMock(title="Workout", start_datetime=now + timedelta(hours=2), end_datetime=now + timedelta(hours=3)),
        ]

    @patch("timeout.views.ai_workload.OpenAI")
    def test_successful_openai_call_returns_warning(self, mock_openai):
        mock_client = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="High workload today: 2 events"))]
        mock_client.chat.completions.create.return_value = mock_response

        warning = get_ai_workload_warning(self.user, self.events)
        self.assertIn("High workload", warning)

    @patch("timeout.views.ai_workload.OpenAI")
    def test_cached_warning_is_returned(self, mock_openai):
        cache_key = f"ai_workload_warning_{self.user.id}_{datetime.now().date()}"
        cache.set(cache_key, "Cached warning", timeout=3600)

        warning = get_ai_workload_warning(self.user, self.events)
        self.assertEqual(warning, "Cached warning")
        mock_openai.assert_not_called()

    @patch("timeout.views.ai_workload.OpenAI")
    def test_no_events_returns_none(self, mock_openai):
        warning = get_ai_workload_warning(self.user, [])
        self.assertIsNone(warning)
        mock_openai.assert_not_called()

    @patch("timeout.views.ai_workload.OpenAI")
    @patch("django.conf.settings.OPENAI_API_KEY", new=None)
    def test_no_api_key_returns_none(self, mock_openai):
        warning = get_ai_workload_warning(self.user, self.events)
        self.assertIsNone(warning)
        mock_openai.assert_not_called()

    @patch("timeout.views.ai_workload.OpenAI")
    def test_openai_exception_returns_none(self, mock_openai):
        cache.clear()

        mock_client = mock_openai.return_value
        mock_client.chat.completions.create.side_effect = Exception("API error")

        warning = get_ai_workload_warning(self.user, self.events)
        self.assertIsNone(warning)