"""
test_check_site.py - Defines CheckSiteCommandTests for testing the check_site management command,
covering active site/SocialApp configuration reporting, missing records, settings override checks,
and Google SocialApp client_id and site linkage validation.
"""


from io import StringIO
from unittest.mock import patch, MagicMock

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase, override_settings


class CheckSiteCommandTests(TestCase):
    """Tests for the check_site management command."""

    def _run(self):
        """Run the management command and return captured stdout."""
        out = StringIO()
        call_command('check_site', stdout=out)
        return out.getvalue()

    @override_settings(SITE_ID=1)
    def test_prints_active_site_when_found(self):
        """Check that the command prints the active site when found."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('example.com', output)

    @override_settings(SITE_ID=1)
    def test_prints_site_id_from_settings(self):
        """Check that the command prints the site ID from settings."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('SITE_ID', output)
        self.assertIn('1', output)

    @override_settings(SITE_ID=999)
    def test_reports_problem_when_site_id_not_found(self):
        """Check that the command reports a problem when the site ID is not found."""
        Site.objects.filter(id=999).delete()
        output = self._run()
        self.assertIn('PROBLEM', output)
        self.assertIn('999', output)

    @override_settings(SITE_ID=1)
    def test_reports_no_site_records_in_db(self):
        """Check that the command reports when there are no Site records in the database."""
        Site.objects.all().delete()
        output = self._run()
        self.assertIn('No Site records', output)

    @override_settings(SITE_ID=1)
    def test_marks_active_site_with_indicator(self):
        """Check that the command marks the active site with an indicator."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'active.com', 'name': 'Active'})
        output = self._run()
        self.assertIn('active', output)

    @override_settings(SITE_ID=1)
    def test_reports_no_social_apps(self):
        """Check that the command reports when there are no SocialApp records."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        with patch('allauth.socialaccount.models.SocialApp.objects') as mock_mgr:
            mock_mgr.all.return_value.exists.return_value = False
            output = self._run()
        self.assertIn('No SocialApp records', output)

    @override_settings(SITE_ID=1)
    def test_correctly_configured_google_app_shows_ok(self):
        """Check that a correctly configured Google app shows OK."""
        site = Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})[0]

        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.provider = 'google'
        mock_app.name = 'Google'
        mock_app.client_id = 'real-client-id'
        mock_app.sites.values_list.return_value = [site.id]

        with patch('allauth.socialaccount.models.SocialApp.objects') as mock_mgr:
            mock_mgr.all.return_value.exists.return_value = True
            mock_mgr.all.return_value.__iter__ = lambda s: iter([mock_app])
            output = self._run()

        self.assertIn('OK', output)

    @override_settings(SITE_ID=1)
    def test_empty_google_client_id_shows_problem(self):
        """Check that an empty Google client_id shows a problem."""
        site = Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})[0]

        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.provider = 'google'
        mock_app.name = 'Google'
        mock_app.client_id = ''
        mock_app.sites.values_list.return_value = [site.id]

        with patch('allauth.socialaccount.models.SocialApp.objects') as mock_mgr:
            mock_mgr.all.return_value.exists.return_value = True
            mock_mgr.all.return_value.__iter__ = lambda s: iter([mock_app])
            output = self._run()

        self.assertIn('PROBLEM', output)
        self.assertIn('client_id', output)

    @override_settings(SITE_ID=1)
    def test_google_app_not_linked_to_site_shows_problem(self):
        """Check that a Google app not linked to the site shows a problem."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})

        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.provider = 'google'
        mock_app.name = 'Google'
        mock_app.client_id = 'real-client-id'
        mock_app.sites.values_list.return_value = []  

        with patch('allauth.socialaccount.models.SocialApp.objects') as mock_mgr:
            mock_mgr.all.return_value.exists.return_value = True
            mock_mgr.all.return_value.__iter__ = lambda s: iter([mock_app])
            output = self._run()

        self.assertIn('PROBLEM', output)
        self.assertIn('linked', output)

    @override_settings(
        SITE_ID=1,
        SOCIALACCOUNT_PROVIDERS={}
    )

    def test_no_app_override_shows_ok(self):
        """Check that no app override shows OK."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('No "APP" override', output)

    @override_settings(
        SITE_ID=1,
        SOCIALACCOUNT_PROVIDERS={'google': {'APP': {'client_id': 'from-settings', 'secret': 'x'}}}
    )

    def test_app_override_with_client_id_shows_warning(self):
        """Check that an app override with a client_id shows a warning."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('settings.py', output)

    @override_settings(
        SITE_ID=1,
        SOCIALACCOUNT_PROVIDERS={'google': {'APP': {'client_id': '', 'secret': ''}}}
    )
    def test_app_override_with_empty_client_id_shows_problem(self):
        """Check that an app override with an empty client_id shows a problem."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('PROBLEM', output)
        self.assertIn('EMPTY client_id', output)

    @override_settings(
        SITE_ID=1,
        SOCIALACCOUNT_STORE_TOKENS=True,
        SOCIALACCOUNT_LOGIN_ON_GET=False,
    )
    def test_prints_other_settings(self):
        """Check that the command prints other relevant settings."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        output = self._run()
        self.assertIn('SOCIALACCOUNT_STORE_TOKENS', output)
        self.assertIn('SOCIALACCOUNT_LOGIN_ON_GET', output)

    @override_settings(SITE_ID=1)
    def test_command_completes_without_error(self):
        """Command should never raise — always print and exit cleanly."""
        Site.objects.get_or_create(id=1, defaults={'domain': 'example.com', 'name': 'Example'})
        try:
            self._run()
        except Exception as e:
            self.fail(f'check_site raised an exception: {e}')