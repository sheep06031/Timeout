from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages


class BannedUserMiddleware:
    """Log out banned users and redirect them to the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'is_banned', False)
            and request.path != '/banned/'
        ):
            logout(request)
            return redirect('/banned/')
        return self.get_response(request)
