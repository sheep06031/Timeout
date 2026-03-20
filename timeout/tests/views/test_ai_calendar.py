import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from timeout.models.event import Event

User = get_user_model()

VALID_AI_RESPONSE = json.dumps({
    'title': 'Test Meeting',
    'event_type': 'meeting',
    'start_datetime': '2099-06-01T09:00',
    'end_datetime': '2099-06-01T10:00',
    'location': 'Room 1',
    'description': '',
    'recurrence': 'none',
    'is_all_day': False,
    'visibility': 'private',
})


def make_mock_openai(content):
    """Return a patched OpenAI class whose client returns `content` as the AI message."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_resp
    mock_openai = MagicMock(return_value=mock_client)
    return mock_openai


@override_settings(OPENAI_API_KEY='test-key')
class AiCreateEventTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.url = reverse('ai_event_create')

    # Authentication 
    def test_login_required(self):
        response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # HTTP method 
    def test_get_not_allowed(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # Input validation 
    def test_empty_input_returns_400(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {'user_input': ''})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('No input provided', response.json()['error'])

    def test_whitespace_only_input_returns_400(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {'user_input': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_missing_input_returns_400(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    # API key 
    @override_settings(OPENAI_API_KEY='')
    def test_no_api_key_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('OpenAI API key not configured', response.json()['error'])

    # Successful creation
    @patch('openai.OpenAI', new_callable=lambda: lambda: make_mock_openai(VALID_AI_RESPONSE))
    def test_successful_event_creation(self, _):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(VALID_AI_RESPONSE)):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow at 9am'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(Event.objects.filter(creator=self.user, title='Test Meeting').exists())

    def test_response_contains_event_fields(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(VALID_AI_RESPONSE)):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow at 9am'})
        event_data = response.json()['event']
        self.assertIn('title', event_data)
        self.assertIn('start', event_data)
        self.assertIn('end', event_data)
        self.assertIn('event_type', event_data)

    # all-day event
    def test_all_day_event_sets_midnight_times(self):
        all_day_response = json.dumps({
            'title': 'All Day Event',
            'event_type': 'other',
            'start_datetime': '2099-06-01T09:00',
            'end_datetime': '2099-06-01T10:00',
            'location': '',
            'description': '',
            'recurrence': 'none',
            'is_all_day': True,
            'visibility': 'private',
        })
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(all_day_response)):
            response = self.client.post(self.url, {'user_input': 'all day event on June 1st'})
        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(creator=self.user, title='All Day Event')
        self.assertEqual(event.start_datetime.hour, 0)
        self.assertEqual(event.start_datetime.minute, 0)
        self.assertEqual(event.end_datetime.hour, 23)
        self.assertEqual(event.end_datetime.minute, 59)

    # ── Markdown stripping ────────────────────────────────────

    def test_markdown_fenced_response_is_parsed(self):
        fenced = f'```json\n{VALID_AI_RESPONSE}\n```'
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(fenced)):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertTrue(response.json()['success'])

    def test_markdown_fenced_without_json_label_is_parsed(self):
        fenced = f'```\n{VALID_AI_RESPONSE}\n```'
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(fenced)):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertTrue(response.json()['success'])

    # error handling
    def test_invalid_json_from_ai_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai('this is not json')):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI returned an invalid response', response.json()['error'])

    def test_openai_exception_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        mock_openai = MagicMock(side_effect=Exception('Connection failed'))
        with patch('openai.OpenAI', mock_openai):
            response = self.client.post(self.url, {'user_input': 'meeting tomorrow'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI error', response.json()['error'])

    def test_model_validation_error_returns_400(self):
        bad_response = json.dumps({
            'title': 'Bad Event',
            'event_type': 'other',
            'start_datetime': 'not-a-datetime',
            'end_datetime': 'also-not-a-datetime',
            'location': '',
            'description': '',
            'recurrence': 'none',
            'is_all_day': False,
            'visibility': 'private',
        })
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(bad_response)):
            response = self.client.post(self.url, {'user_input': 'bad event'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
