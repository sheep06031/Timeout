"""
signals.py - Defines signal handlers for user-related events, such as linking a social account,
to provide user feedback via Django's messaging framework.
"""


from django.contrib import messages
from django.dispatch import receiver

from allauth.socialaccount.signals import social_account_added


@receiver(social_account_added)
def on_social_account_linked(request, sociallogin, **kwargs):
    """Notify the user when a social account is successfully linked."""
    provider = sociallogin.account.get_provider().name
    messages.success(
        request,
        f'Your {provider} account has been linked successfully!',
    )
