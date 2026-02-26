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
        return resolve_url('complete_profile')

    def get_login_redirect_url(self, request):
        """
        After email/password login, redirect to "Complete Profile" if
        essential fields are missing, otherwise go to the dashboard.
        """
        user = request.user
        if TimeoutSocialAccountAdapter._profile_incomplete(user):
            return resolve_url('complete_profile')
        return resolve_url('dashboard')


class TimeoutSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter that handles:
    1. Automatic email-based linking of social accounts to existing local users.
    2. Redirecting new social users to a "Complete Profile" page when required
       fields are missing.
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

    def get_signup_redirect_url(self, request):
        """
        After a new social user is auto-created (SOCIALACCOUNT_AUTO_SIGNUP = True),
        send them straight to the profile-completion page to pick a username, etc.
        This bypasses the default /accounts/social/signup/ form entirely.
        """
        return resolve_url('complete_profile')

    def get_login_redirect_url(self, request):
        """
        After social login, redirect to "Complete Profile" if the user
        is missing required profile fields, otherwise go to the dashboard.
        """
        user = request.user
        if self._profile_incomplete(user):
            return resolve_url('complete_profile')
        return resolve_url('dashboard')

    @staticmethod
    def _profile_incomplete(user):
        """Check if any essential profile fields are missing."""
        return not all([
            user.username and not user.username.startswith('user_'),
            user.university,
            user.year_of_study,
        ])
