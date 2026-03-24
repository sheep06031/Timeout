from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages


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
            and request.path != '/accounts/login/'
        ):
            logout(request)
            messages.error(
                request,
                'Your account has been suspended. Contact support if you believe this is an error.',
            )
            return redirect('/accounts/login/')
        return self.get_response(request)
