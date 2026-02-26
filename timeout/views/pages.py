from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing(request):
    """Landing page view. Authenticated users go straight to the dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'pages/landing.html')


@login_required
def dashboard(request):
    """Dashboard page view."""
    return render(request, 'pages/dashboard.html')


@login_required
def profile(request):
    """Profile page view."""
    return render(request, 'pages/profile.html')


@login_required
def calendar(request):
    """Calendar page view."""
    return render(request, 'pages/calendar.html')


@login_required
def notes(request):
    """Notes page view."""
    return render(request, 'pages/notes.html')


@login_required
def statistics(request):
    """Statistics page view."""
    return render(request, 'pages/statistics.html')


@login_required
def social(request):
    """Social page view."""
    return render(request, 'pages/social.html')
