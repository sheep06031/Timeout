"""
Views for the main pages of the Timeout app, including dashboard, profile, calendar, statistics, and social feed.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from timeout.models import User, Note, Message, Conversation
from timeout.models.like import Like
from timeout.models.bookmark import Bookmark
from timeout.services import FeedService, DeadlineService, EventService
from timeout.views.statistics import get_focus_stats, build_context
from timeout.views.profile import get_profile_event
from timeout.services.ai_service import AIService


def banned(request):
    """Banned page view."""
    return render(request, 'banned.html')


def landing(request):
    """Landing page view. Authenticated users go straight to the dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'pages/landing.html')


def _dashboard_schedule(user):
    """Schedule widget: upcoming events, deadlines, recent notes."""
    return {
        'upcoming_events': EventService.get_dashboard_upcoming(user),
        'recent_notes': Note.objects.filter(owner=user).order_by('-updated_at')[:4],
        'deadlines': DeadlineService.get_active_deadlines(user)[:5],
    }


def _dashboard_messaging(user):
    """Messaging widget: unread message count."""
    conversations = Conversation.objects.filter(participants=user)
    unread_count = Message.objects.filter(
        conversation__in=conversations,
        is_read=False,
    ).exclude(sender=user).count()
    return {'unread_count': unread_count}


def _dashboard_social(user):
    """Social + AI widgets: feed posts and AI briefing."""
    return {
        'social_posts': FeedService.get_following_feed(user)[:4],
        'ai_briefing': AIService.get_dashboard_briefing(user),
    }


def _build_dashboard_context(user, greeting):
    """Assemble context dict for the dashboard page."""
    return {
        'greeting': greeting,
        **_dashboard_schedule(user),
        **_dashboard_messaging(user),
        **_dashboard_social(user),
        **get_focus_stats(user),
    }


@login_required
def dashboard(request):
    """Dashboard page view."""
    user = request.user
    local_hour = timezone.localtime(timezone.now()).hour
    if local_hour < 12:
        greeting = 'Good morning'
    elif local_hour < 18:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'
    context = _build_dashboard_context(user, greeting)
    return render(request, 'pages/dashboard.html', context)


@login_required
def profile(request):
    """Profile page view."""
    posts = FeedService.get_user_posts(request.user, request.user)
    event, event_status = get_profile_event(request.user)
    friends_count = request.user.following.filter(following=request.user).count()

    context = {
        'posts': posts,
        'status_choices': User.Status.choices,
        'event': event,
        'event_status': event_status,
        'friends_count': friends_count,
        'liked_ids': set(Like.objects.filter(user=request.user).values_list('post_id', flat=True)),
        'bookmarked_ids': set(Bookmark.objects.filter(user=request.user).values_list('post_id', flat=True)),
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
