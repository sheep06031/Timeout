"""
Defines a custom template tag to check if Google OAuth is available by verifying the existence of a configured SocialApp with credentials.
"""


import os
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_oauth_available():
    """Return True when Google OAuth credentials are available.

    Checks two sources in order:
    1. Environment variables (GOOGLE_CLIENT_ID) — set via .env
    2. A configured SocialApp in the database (Django Admin ▸ Social Applications)
    """
    if os.environ.get('GOOGLE_CLIENT_ID'):
        return True

    # Fallback: credentials stored in the database
    try:
        from allauth.socialaccount.models import SocialApp
        app = SocialApp.objects.filter(
            provider='google',
            sites__id=settings.SITE_ID,
        ).first()
        return app is not None and bool(app.client_id)
    except Exception:
        return False
