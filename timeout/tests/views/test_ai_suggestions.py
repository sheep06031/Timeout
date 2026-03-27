from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from timeout.views.ai_suggestions import get_ai_suggestions

User = get_user_model()


class AiSuggestionsHelperTests(TestCase):

    def setUp(self):
        cache.clear() 
        self.user = User.objects.create_user(username="testuser", password="pass123")
        now = datetime.now()
        self.events = [
            MagicMock(title="Meeting", start_datetime=now, end_datetime=now + timedelta(hours=1)),
            MagicMock(title="Workout", start_datetime=now + timedelta(hours=2), end_datetime=now + timedelta(hours=3)),
        ]

    @patch("timeout.views.ai_suggestions.OpenAI")
    def test_successful_openai_call_returns_suggestions(self, mock_openai):
        mock_client = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps([
            "Take a 10-min break after your meeting",
            "Schedule workout first thing in the morning"
        ])))]
        mock_client.chat.completions.create.return_value = mock_response

        suggestions = get_ai_suggestions(self.user, self.events)
        self.assertIn("Take a 10-min break after your meeting", suggestions)
        self.assertIn("Schedule workout first thing in the morning", suggestions)

    @patch("timeout.views.ai_suggestions.OpenAI")
    def test_cached_suggestions_returned(self, mock_openai):
        cache_key = f"ai_suggestions_{self.user.id}_{datetime.now().date()}"
        cache.set(cache_key, ["Cached suggestion"], timeout=3600)

        suggestions = get_ai_suggestions(self.user, self.events)
        self.assertEqual(suggestions, ["Cached suggestion"])
        mock_openai.assert_not_called()

    def test_no_events_returns_default_message(self):
        suggestions = get_ai_suggestions(self.user, [])
        self.assertEqual(suggestions, ["No events today. You have free time!"])

    @patch("timeout.views.ai_suggestions.OpenAI")
    def test_invalid_json_returns_error_message(self, mock_openai):
        mock_client = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Not JSON"))]
        mock_client.chat.completions.create.return_value = mock_response

        suggestions = get_ai_suggestions(self.user, self.events)
        self.assertEqual(suggestions, ["AI returned invalid JSON. Please try again."])

    @patch("timeout.views.ai_suggestions.OpenAI")
    def test_openai_exception_returns_unavailable_message(self, mock_openai):
        mock_client = mock_openai.return_value
        mock_client.chat.completions.create.side_effect = Exception("API error")

        suggestions = get_ai_suggestions(self.user, self.events)
        self.assertEqual(suggestions, ["AI suggestion unavailable: API error"])