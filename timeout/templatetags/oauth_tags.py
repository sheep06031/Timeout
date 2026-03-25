from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_oauth_available():
    """Return True only when a Google SocialApp with credentials exists."""
    try:
        from allauth.socialaccount.models import SocialApp
        app = SocialApp.objects.filter(
            provider='google',
            sites__id=settings.SITE_ID,
        ).first()
        return app is not None and bool(app.client_id)
    except Exception:
        return False
