"""
Defines a custom template tag to check if Google OAuth is available by verifying the existence of a configured SocialApp with credentials.
"""


import os
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_oauth_available():
    """Return True if Google OAuth is available (credentials in settings or DB)."""
    provider_cfg = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}).get('google', {})
    if 'APP' in provider_cfg:
        try:
            from allauth.socialaccount.models import SocialApp
            SocialApp.objects.filter(provider='google').delete()
        except Exception:
            pass
        return True
    if os.environ.get('GOOGLE_CLIENT_ID'):
        return True
    try:
        from allauth.socialaccount.models import SocialApp
        app = SocialApp.objects.filter(
            provider='google',
            sites__id=settings.SITE_ID,
        ).first()
        return app is not None and bool(app.client_id)
    except Exception:
        return False
