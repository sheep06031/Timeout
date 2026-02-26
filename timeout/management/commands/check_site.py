"""
Diagnostic command to verify Site + SocialApp configuration for allauth.

Usage:
    python manage.py check_site

Checks:
  1. All Site records vs SITE_ID in settings.
  2. All SocialApp records and whether they are linked to the active Site.
  3. Whether the Google SocialApp has a non-empty client_id.
  4. Whether SOCIALACCOUNT_PROVIDERS['google'] has an 'APP' dict that would
     override the database credentials.
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Diagnose Site and Google SocialApp configuration for allauth.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 1. SITE_ID check ==='))
        site_id = getattr(settings, 'SITE_ID', None)
        self.stdout.write(f'  settings.SITE_ID = {site_id}')

        sites = Site.objects.all().order_by('id')
        if not sites.exists():
            self.stdout.write(self.style.ERROR('  No Site records in the database!'))
        else:
            for s in sites:
                marker = ' <-- active' if s.id == site_id else ''
                self.stdout.write(f'  Site(id={s.id}, domain="{s.domain}", name="{s.name}"){marker}')

        try:
            active_site = Site.objects.get(id=site_id)
            self.stdout.write(self.style.SUCCESS(
                f'  OK: Active site found → {active_site.domain}'
            ))
        except Site.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'  PROBLEM: No Site with id={site_id} exists! '
                f'Run "python manage.py init_site" to fix.'
            ))
            active_site = None

        # ── 2. SocialApp check ──────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 2. SocialApp check ==='))
        try:
            from allauth.socialaccount.models import SocialApp
        except ImportError:
            self.stdout.write(self.style.ERROR(
                '  allauth.socialaccount is not installed.'
            ))
            return

        apps = SocialApp.objects.all()
        if not apps.exists():
            self.stdout.write(self.style.ERROR(
                '  No SocialApp records found! '
                'Go to Django Admin → Social Applications → Add one for Google.'
            ))
        else:
            for app in apps:
                linked_site_ids = list(app.sites.values_list('id', flat=True))
                has_client_id = bool(app.client_id and app.client_id.strip())
                self.stdout.write(
                    f'  SocialApp(id={app.id}, provider="{app.provider}", '
                    f'name="{app.name}", '
                    f'client_id={"SET" if has_client_id else "EMPTY"}, '
                    f'linked_sites={linked_site_ids})'
                )
                if app.provider == 'google':
                    if not has_client_id:
                        self.stdout.write(self.style.ERROR(
                            '    PROBLEM: Google SocialApp has an EMPTY client_id!'
                        ))
                    if active_site and active_site.id not in linked_site_ids:
                        self.stdout.write(self.style.ERROR(
                            f'    PROBLEM: Google SocialApp is NOT linked to '
                            f'Site id={site_id} ({active_site.domain}). '
                            f'Fix in Admin → Social Applications → Sites.'
                        ))
                    elif active_site and active_site.id in linked_site_ids and has_client_id:
                        self.stdout.write(self.style.SUCCESS(
                            '    OK: Google SocialApp is correctly configured.'
                        ))

        # ── 3. Settings override check ──────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== 3. SOCIALACCOUNT_PROVIDERS override check ==='
        ))
        providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
        google_conf = providers.get('google', {})
        if 'APP' in google_conf:
            app_dict = google_conf['APP']
            cid = app_dict.get('client_id', '')
            if not cid:
                self.stdout.write(self.style.ERROR(
                    '  PROBLEM: SOCIALACCOUNT_PROVIDERS["google"]["APP"] exists '
                    'with an EMPTY client_id.\n'
                    '  This OVERRIDES the database SocialApp and sends no '
                    'client_id to Google!\n'
                    '  FIX: Remove the "APP" dict from settings.py and use '
                    'Django Admin instead.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  INFO: client_id is set in settings.py (starts with '
                    f'"{cid[:12]}..."). Database SocialApp will be IGNORED.'
                ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '  OK: No "APP" override in settings — credentials will be '
                'read from the database SocialApp.'
            ))

        # ── 4. SOCIALACCOUNT_STORE_TOKENS ───────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== 4. Other settings ==='
        ))
        store = getattr(settings, 'SOCIALACCOUNT_STORE_TOKENS', None)
        self.stdout.write(f'  SOCIALACCOUNT_STORE_TOKENS = {store}')
        login_on_get = getattr(settings, 'SOCIALACCOUNT_LOGIN_ON_GET', None)
        self.stdout.write(f'  SOCIALACCOUNT_LOGIN_ON_GET = {login_on_get}')

        self.stdout.write('')
