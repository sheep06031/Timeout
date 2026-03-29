"""
apps.py - Application configuration for the Timeout Django app.
Registers the app and imports signal handlers on startup.
"""

from django.apps import AppConfig

class TimeoutConfig(AppConfig):
    """Django AppConfig for the Timeout application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timeout'

    def ready(self):
        """Import signal handlers and clean up duplicate Google SocialApp records."""
        self._deduplicate_google_socialapp()

    @staticmethod
    def _deduplicate_google_socialapp():
        """Remove DB SocialApp for Google when settings already provides APP credentials.

        allauth raises MultipleObjectsReturned if both a settings-based APP
        dict and a database SocialApp exist for the same provider.
        """
        from django.conf import settings

        provider_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}).get('google', {})
        if 'APP' not in provider_cfg:
            return

        try:
            from allauth.socialaccount.models import SocialApp
            SocialApp.objects.filter(provider='google').delete()
        except Exception:
            pass
