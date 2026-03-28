"""
middleware.py - Custom middleware to handle banned users.

This middleware checks if the authenticated user is marked as banned
(via an `is_banned` attribute on the User model). If so, it logs them 
out and redirects them to a dedicated "banned" page. This ensures that 
banned users cannot access any part of the site and are informed of their status.
"""


from django.contrib.auth import logout
from django.shortcuts import redirect


class BannedUserMiddleware:
    """Log out banned users and redirect them to the login page."""

    def __init__(self, get_response):
        """Initialize middleware with response handler."""
        self.get_response = get_response

    def __call__(self, request):
        """Check if user is banned and log them out if so."""
        if (
            request.user.is_authenticated
            and getattr(request.user, 'is_banned', False)
            and request.path != '/banned/'
        ):
            logout(request)
            return redirect('/banned/')
        return self.get_response(request)
