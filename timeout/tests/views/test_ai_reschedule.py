import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from timeout.models.event import Event

User = get_user_model()


def make_session(creator, title='Study Session', hours_from_now=24, duration_hours=2):
    """Create an upcoming study session."""
    now = timezone.now()
    start = now + timedelta(hours=hours_from_now)
    return Event.objects.create(
        creator=creator,
        title=title,
        event_type=Event.EventType.STUDY_SESSION,
        status=Event.EventStatus.UPCOMING,
        start_datetime=start,
        end_datetime=start + timedelta(hours=duration_hours),
    )


def make_mock_openai(content):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_resp
    return MagicMock(return_value=mock_client)


@override_settings(OPENAI_API_KEY='test-key')
class RescheduleStudySessionsTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.url = reverse('reschedule_study_sessions')

    # authentication 
    def test_login_required(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # http method 
    def test_get_not_allowed(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # no sessions 
    def test_no_sessions_returns_400(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('No upcoming study sessions found', response.json()['error'])

    def test_cancelled_sessions_not_counted(self):
        session = make_session(self.user)
        session.status = Event.EventStatus.CANCELLED
        session.save()
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_sessions_beyond_21_days_excluded(self):
        make_session(self.user, hours_from_now=22 * 24)  # 22 days away
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    # successful reschedule 
    def test_successful_reschedule_returns_suggestions(self):
        session = make_session(self.user)
        ai_suggestions = json.dumps([{
            'id': session.pk,
            'title': session.title,
            'start': '2099-06-01T10:00',
            'end': '2099-06-01T12:00',
        }])
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(ai_suggestions)):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('suggestions', data)
        self.assertIn('original', data)

    def test_original_contains_session_data(self):
        session = make_session(self.user, title='Maths Revision')
        ai_suggestions = json.dumps([{
            'id': session.pk,
            'title': session.title,
            'start': '2099-06-01T10:00',
            'end': '2099-06-01T12:00',
        }])
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(ai_suggestions)):
            response = self.client.post(self.url)
        original = response.json()['original']
        self.assertEqual(len(original), 1)
        self.assertEqual(original[0]['id'], session.pk)
        self.assertEqual(original[0]['title'], 'Maths Revision')
        self.assertIn('start', original[0])
        self.assertIn('end', original[0])

    # error handling 
    def test_invalid_json_returns_500(self):
        make_session(self.user)
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai('not valid json')):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI returned an invalid response', response.json()['error'])

    def test_openai_exception_returns_500(self):
        make_session(self.user)
        self.client.login(username='testuser', password='pass1234')
        mock_openai = MagicMock(side_effect=Exception('API down'))
        with patch('openai.OpenAI', mock_openai):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI error', response.json()['error'])

    # markdown stripping (lines 95-97)
    def test_markdown_fenced_response_is_parsed(self):
        session = make_session(self.user)
        ai_suggestions = json.dumps([{
            'id': session.pk,
            'title': session.title,
            'start': '2099-06-01T10:00',
            'end': '2099-06-01T12:00',
        }])
        fenced = f'```json\n{ai_suggestions}\n```'
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(fenced)):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])


@override_settings(OPENAI_API_KEY='test-key')
class AiSuggestRescheduleTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.other = User.objects.create_user(username='other', password='pass1234')
        now = timezone.now()
        self.session = Event.objects.create(
            creator=self.user,
            title='Python Revision',
            event_type=Event.EventType.STUDY_SESSION,
            status=Event.EventStatus.UPCOMING,
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(hours=1),
        )
        self.url = reverse('ai_reschedule')
        self.valid_ai_response = json.dumps({
            'start_datetime': '2099-06-02T10:00',
            'end_datetime': '2099-06-02T11:00',
            'reason': 'Free slot found in the morning',
        })

    # Authentication 
    def test_login_required(self):
        response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # HTTP method 
    def test_get_not_allowed(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # Input validation 
    def test_missing_event_id_returns_400(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('No event ID provided', response.json()['error'])

    # API key 
    @override_settings(OPENAI_API_KEY='')
    def test_no_api_key_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 500)
        self.assertIn('OpenAI API key not configured', response.json()['error'])

    # Event lookup 
    def test_nonexistent_event_returns_404(self):
        self.client.login(username='testuser', password='pass1234')
        response = self.client.post(self.url, {'event_id': 99999})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])

    def test_other_users_event_returns_404(self):
        self.client.login(username='other', password='pass1234')
        response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])

    # successful suggestion 
    def test_successful_suggestion_returns_200(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(self.valid_ai_response)):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('suggestion', data)

    def test_suggestion_contains_correct_fields(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(self.valid_ai_response)):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        suggestion = response.json()['suggestion']
        self.assertEqual(suggestion['title'], 'Python Revision')
        self.assertEqual(suggestion['start_datetime'], '2099-06-02T10:00')
        self.assertEqual(suggestion['end_datetime'], '2099-06-02T11:00')
        self.assertEqual(suggestion['reason'], 'Free slot found in the morning')
        self.assertEqual(suggestion['event_type'], 'study_session')

    def test_suggestion_uses_event_title(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(self.valid_ai_response)):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.json()['suggestion']['title'], self.session.title)

    # markdown stripping 
    def test_markdown_fenced_response_is_parsed(self):
        fenced = f'```json\n{self.valid_ai_response}\n```'
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai(fenced)):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertTrue(response.json()['success'])

    # error handling 
    def test_invalid_json_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        with patch('openai.OpenAI', make_mock_openai('not valid json at all')):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI returned an invalid response', response.json()['error'])

    def test_openai_exception_returns_500(self):
        self.client.login(username='testuser', password='pass1234')
        mock_openai = MagicMock(side_effect=Exception('Timeout'))
        with patch('openai.OpenAI', mock_openai):
            response = self.client.post(self.url, {'event_id': self.session.pk})
        self.assertEqual(response.status_code, 500)
        self.assertIn('AI error', response.json()['error'])
