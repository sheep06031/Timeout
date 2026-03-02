from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from timeout.models import User
from timeout.services import FeedService
from timeout.views.statistics import build_context
from timeout.views.profile import get_profile_event



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
    posts = FeedService.get_user_posts(request.user, request.user)
    event, event_status = get_profile_event(request.user)
    context = {
        'posts': posts,
        'status_choices': User.Status.choices,
        'event': event,
        'event_status': event_status,
    }
    return render(request, 'pages/profile.html', context)

@login_required
def calendar(request):
    """Calendar page view."""
    return render(request, 'pages/calendar.html')


@login_required
def statistics(request):
    """Statistics page view."""
    context = build_context(request.user)
    return render(request, 'pages/statistics.html', context)


@login_required
def social(request):
    """Social page view."""
    return render(request, 'pages/social.html')
