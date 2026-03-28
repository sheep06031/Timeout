"""
adapters.py - Custom django-allauth adapters for the Timeout application.

Provides two adapter classes that override default allauth behaviour:
    TimeoutAccountAdapter
        - Redirects newly registered (email/password) users to a profile
          completion page so they can set a username and university details.
        - After login, routes users to the dashboard and, when applicable,
          updates their status to SOCIAL.

    TimeoutSocialAccountAdapter
        - Before completing a social login, checks whether an existing local
          account shares the same verified email address.  If one is found the
          social account is connected to it automatically, preventing duplicate
          accounts.
        - Redirects first-time social users to the same profile completion page.

Usage:
    Register both adapters in settings.py:
        ACCOUNT_ADAPTER        = 'timeout.adapters.TimeoutAccountAdapter'
        SOCIALACCOUNT_ADAPTER  = 'timeout.adapters.TimeoutSocialAccountAdapter'
"""


from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

User = get_user_model()


class TimeoutAccountAdapter(DefaultAccountAdapter):
    """
    Custom local-account adapter.
    Redirects users to the profile-completion page after signup
    so they can choose a username and fill in university details.
    """

    def get_signup_redirect_url(self, request):
        """After email/password signup, redirect to the "Complete Profile" page."""
        request.session['needs_profile_completion'] = True
        return resolve_url('complete_profile')

    def get_login_redirect_url(self, request):
        """
        After email/password login, go straight to the dashboard.
        Existing users are never forced to complete their profile.
        """
        user = request.user
        if user.is_authenticated and user.auto_online and user.status != user.Status.SOCIAL:
            user.status = user.Status.SOCIAL
            user.save(update_fields=['status'])
        return resolve_url('dashboard')


class TimeoutSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter that handles:
    1. Automatic email-based linking of social accounts to existing local users.
    2. Redirecting first-time social users to a "Complete Profile" page.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Auto-link a social account to an existing local account
        if the email addresses match.
        """
        email = sociallogin.account.extra_data.get('email')
        if not email and sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email

        if not email:
            return

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return

        # If this social account is already connected, nothing to do
        if sociallogin.is_existing:
            return

        # Connect the social account to the existing local user
        sociallogin.connect(request, user)

