"""
test_ai_service.py - Defines AIServiceTests for testing the AIService's get_dashboard_briefing method, including caching behavior, OpenAI interactions,
handling of unauthenticated users, and correct inclusion of user stats in the prompt sent to OpenAI.
"""


from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils import timezone

from timeout.models import Event
from timeout.services.ai_service import AIService

User = get_user_model()

BRIEFING_TEXT = 'Great week! Keep it up.'


def make_mock_openai(content=BRIEFING_TEXT):
    """Helper to create a mock OpenAI client that returns the specified content."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_resp
    return MagicMock(return_value=mock_client)


def make_event(user, event_type, hours_ago=3, duration_hours=2, is_completed=False, end_in_past=False):
    """Helper to create an event with the specified parameters."""
    now = timezone.now()
    start = now - timedelta(hours=hours_ago)
    end = start + timedelta(hours=duration_hours)
    if end_in_past:
        end = now - timedelta(hours=1)
    return Event.objects.create(
        creator=user,
        title='Test Event',
        event_type=event_type,
        start_datetime=start,
        end_datetime=end,
        is_completed=is_completed,
    )


@override_settings(OPENAI_API_KEY='test-key')
class AIServiceTests(TestCase):
    """Tests for AIService.get_dashboard_briefing() and related logic."""

    def setUp(self):
        """Set up a test user for AIService tests."""
        self.user = User.objects.create_user(username='testuser', password='pass1234')

    def test_unauthenticated_returns_none(self):
        """Test that unauthenticated users receive None."""
        result = AIService.get_dashboard_briefing(AnonymousUser())
        self.assertIsNone(result)

    @patch('timeout.services.ai_service.cache')
    def test_returns_cached_value_without_openai_call(self, mock_cache):
        """Test that cached values are returned without calling OpenAI."""
        mock_cache.get.return_value = 'cached briefing'
        with patch('openai.OpenAI') as mock_openai:
            result = AIService.get_dashboard_briefing(self.user)
        self.assertEqual(result, 'cached briefing')
        mock_openai.assert_not_called()

    @patch('timeout.services.ai_service.cache')
    def test_caches_result_after_openai_call(self, mock_cache):
        """Test that a cache miss triggers an OpenAI call and caches the result."""
        mock_cache.get.return_value = None
        with patch('openai.OpenAI', make_mock_openai()):
            AIService.get_dashboard_briefing(self.user)
        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args[0]
        self.assertEqual(args[1], BRIEFING_TEXT)
        self.assertEqual(args[2], AIService.CACHE_TIMEOUT)

    @patch('timeout.services.ai_service.cache')
    def test_returns_briefing_text(self, mock_cache):
        """Test that the briefing text is returned correctly."""
        mock_cache.get.return_value = None
        with patch('openai.OpenAI', make_mock_openai()):
            result = AIService.get_dashboard_briefing(self.user)
        self.assertEqual(result, BRIEFING_TEXT)

    @patch('timeout.services.ai_service.cache')
    def test_openai_exception_returns_none(self, mock_cache):
        """Test that an OpenAI exception results in None being returned."""
        mock_cache.get.return_value = None
        mock_openai = MagicMock(side_effect=Exception('API error'))
        with patch('openai.OpenAI', mock_openai):
            with self.assertLogs('timeout.services.ai_service', level='WARNING') as cm:
                result = AIService.get_dashboard_briefing(self.user)
        self.assertIsNone(result)
        self.assertTrue(any('OpenAI briefing call failed' in msg for msg in cm.output))

    @patch('timeout.services.ai_service.cache')
    def test_study_hours_passed_to_openai(self, mock_cache):
        """Test that study hours are correctly passed to OpenAI."""
        mock_cache.get.return_value = None
        make_event(self.user, Event.EventType.STUDY_SESSION, hours_ago=3, duration_hours=2)

        captured = {}

        def fake_create(**kwargs):
            """Fake OpenAI create method to capture prompt."""
            captured['prompt'] = kwargs['messages'][1]['content']
            resp = MagicMock()
            resp.choices[0].message.content = BRIEFING_TEXT
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create
        with patch('openai.OpenAI', MagicMock(return_value=mock_client)):
            AIService.get_dashboard_briefing(self.user)

        self.assertIn('total_study_hours', captured['prompt'])
        self.assertIn('2.0', captured['prompt'])

    @patch('timeout.services.ai_service.cache')
    def test_missed_deadlines_counted(self, mock_cache):
        """Test that missed deadlines are correctly counted."""
        mock_cache.get.return_value = None
        make_event(
            self.user, Event.EventType.DEADLINE,
            hours_ago=5, duration_hours=1,
            is_completed=False, end_in_past=True,
        )
        captured = {}
        def fake_create(**kwargs):
            """Fake OpenAI create method to capture prompt."""
            captured['prompt'] = kwargs['messages'][1]['content']
            resp = MagicMock()
            resp.choices[0].message.content = BRIEFING_TEXT
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create
        with patch('openai.OpenAI', MagicMock(return_value=mock_client)):
            AIService.get_dashboard_briefing(self.user)

        self.assertIn('"missed_deadlines": 1', captured['prompt'])

    @patch('timeout.services.ai_service.cache')
    def test_most_productive_day_in_stats(self, mock_cache):
        """Test that the most productive day is correctly included in stats."""
        mock_cache.get.return_value = None
        make_event(self.user, Event.EventType.OTHER, hours_ago=2, is_completed=True)
        make_event(self.user, Event.EventType.OTHER, hours_ago=4, is_completed=True)

        captured = {}

        def fake_create(**kwargs):
            """Fake OpenAI create method to capture prompt."""
            captured['prompt'] = kwargs['messages'][1]['content']
            resp = MagicMock()
            resp.choices[0].message.content = BRIEFING_TEXT
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create
        with patch('openai.OpenAI', MagicMock(return_value=mock_client)):
            AIService.get_dashboard_briefing(self.user)

        self.assertIn('most_productive_day', captured['prompt'])

    @patch('timeout.services.ai_service.cache')
    def test_no_completed_events_gives_none_yet(self, mock_cache):
        """Test that no completed events results in 'None yet'."""
        mock_cache.get.return_value = None

        captured = {}

        def fake_create(**kwargs):
            """Fake OpenAI create method to capture prompt."""
            captured['prompt'] = kwargs['messages'][1]['content']
            resp = MagicMock()
            resp.choices[0].message.content = BRIEFING_TEXT
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create
        with patch('openai.OpenAI', MagicMock(return_value=mock_client)):
            AIService.get_dashboard_briefing(self.user)

        self.assertIn('None yet', captured['prompt'])
