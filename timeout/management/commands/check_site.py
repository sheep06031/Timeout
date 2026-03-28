"""
Diagnostic command to verify Site + SocialApp configuration for allauth.

Usage:
    python manage.py check_site

Checks:
  All Site records vs SITE_ID in settings.
  All SocialApp records and whether they are linked to the active Site.
  Whether the Google SocialApp has a non-empty client_id.
  Whether SOCIALACCOUNT_PROVIDERS['google'] has an 'APP' dict that would override the database credentials.
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Management command to diagnose Site and Google SocialApp configuration for allauth."""
    help = 'Diagnose Site and Google SocialApp configuration for allauth.'

    def handle(self, *args, **options):
        """Run all checks and print results."""
        active_site = self._check_site_id()
        self._check_social_apps(active_site)
        self._check_provider_override()
        self._check_other_settings()
        self.stdout.write('')

    def _check_site_id(self):
        """Verify SITE_ID and list all Site records."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 1. SITE_ID check ==='))
        site_id = getattr(settings, 'SITE_ID', None)
        self.stdout.write(f'  settings.SITE_ID = {site_id}')

        # List every Site in the DB, currently active ones marked
        sites = Site.objects.all().order_by('id')
        if not sites.exists():
            self.stdout.write(self.style.ERROR('  No Site records in the database!'))
        else:
            for s in sites:
                marker = ' <-- active' if s.id == site_id else ''
                self.stdout.write(f'  Site(id={s.id}, domain="{s.domain}", name="{s.name}"){marker}')

        try:
            active_site = Site.objects.get(id=site_id)
            self.stdout.write(self.style.SUCCESS(f'  OK: Active site found → {active_site.domain}'))
            return active_site
        except Site.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'  PROBLEM: No Site with id={site_id} exists! '
                f'Run "python manage.py init_site" to fix.'
            ))
            return None

    def _check_social_apps(self, active_site):
        """Check all SocialApp records and validate the Google one."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 2. SocialApp check ==='))
        try:
            from allauth.socialaccount.models import SocialApp
        except ImportError:
            self.stdout.write(self.style.ERROR('  allauth.socialaccount is not installed.'))
            return

        apps = SocialApp.objects.all()
        if not apps.exists():
            self.stdout.write(self.style.ERROR(
                '  No SocialApp records found! '
                'Go to Django Admin → Social Applications → Add one for Google.'
            ))
            return

        site_id = getattr(settings, 'SITE_ID', None)
        for app in apps:
            self._report_social_app(app, active_site, site_id)

    def _report_social_app(self, app, active_site, site_id):
        """Print status for a single SocialApp record."""
        linked_site_ids = list(app.sites.values_list('id', flat=True))
        has_client_id = bool(app.client_id and app.client_id.strip())
        self.stdout.write(
            f'  SocialApp(id={app.id}, provider="{app.provider}", '
            f'name="{app.name}", '
            f'client_id={"SET" if has_client_id else "EMPTY"}, '
            f'linked_sites={linked_site_ids})'
        )
        if app.provider != 'google':
            return
        if not has_client_id:
            self.stdout.write(self.style.ERROR('    PROBLEM: Google SocialApp has an EMPTY client_id!'))
        if active_site and active_site.id not in linked_site_ids:
            self.stdout.write(self.style.ERROR(
                f'    PROBLEM: Google SocialApp is NOT linked to '
                f'Site id={site_id} ({active_site.domain}). '
                f'Fix in Admin → Social Applications → Sites.'
            ))
        elif active_site and active_site.id in linked_site_ids and has_client_id:
            self.stdout.write(self.style.SUCCESS('    OK: Google SocialApp is correctly configured.'))

    def _check_provider_override(self):
        """Warn if settings.py overrides database credentials."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 3. SOCIALACCOUNT_PROVIDERS override check ==='))
        google_conf = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}).get('google', {})

        if 'APP' not in google_conf:
            self.stdout.write(self.style.SUCCESS(
                '  OK: No "APP" override in settings, credentials from database SocialApp.'
            ))
            return

        cid = google_conf['APP'].get('client_id', '')
        if not cid:
            self.stdout.write(self.style.ERROR(
                '  PROBLEM: SOCIALACCOUNT_PROVIDERS["google"]["APP"] has EMPTY client_id.\n'
                '  This OVERRIDES the database SocialApp! Remove "APP" dict from settings.py.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'  INFO: client_id set in settings.py ("{cid[:12]}..."). DB SocialApp ignored.'
            ))

    def _check_other_settings(self):
        """Report other relevant allauth settings."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 4. Other settings ==='))
        store = getattr(settings, 'SOCIALACCOUNT_STORE_TOKENS', None)
        self.stdout.write(f'  SOCIALACCOUNT_STORE_TOKENS = {store}')
        login_on_get = getattr(settings, 'SOCIALACCOUNT_LOGIN_ON_GET', None)
        self.stdout.write(f'  SOCIALACCOUNT_LOGIN_ON_GET = {login_on_get}')
