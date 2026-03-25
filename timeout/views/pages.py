from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from timeout.models import User, Note, Message, Conversation
from timeout.models.event import Event
from timeout.services import FeedService, DeadlineService
from timeout.views.statistics import get_focus_stats, build_context
from timeout.views.profile import get_profile_event
from timeout.services.ai_service import AIService
from timeout.models.notification import Notification


def banned(request):
    return render(request, 'banned.html')


def landing(request):
    """Landing page view. Authenticated users go straight to the dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'pages/landing.html')


@login_required
def dashboard(request):
    """Dashboard page view."""
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    context = {
        "unread_count": unread_count,
    }
    #return render(request, 'pages/dashboard.html')
    user = request.user
    now = timezone.now()

    # Time-aware greeting
    local_hour = timezone.localtime(now).hour
    if local_hour < 12:
        greeting = 'Good morning'
    elif local_hour < 18:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'

    # Upcoming events
    upcoming_events = Event.objects.filter(
        creator=user,
        start_datetime__gte=now,
        status__in=['upcoming', 'ongoing'],
    ).order_by('start_datetime')[:5]

    # Recent notes
    recent_notes = Note.objects.filter(owner=user).order_by('-updated_at')[:4]

    # Deadlines
    deadlines = DeadlineService.get_active_deadlines(user)[:5]

    # Social feed (recent posts from followed users)
    social_posts = FeedService.get_following_feed(user, limit=4)

    # Focus stats (last 7 days)
    focus_stats = get_focus_stats(user)

    # Unread messages count
    user_conversations = Conversation.objects.filter(participants=user)
    unread_count = Message.objects.filter(
        conversation__in=user_conversations,
        is_read=False,
    ).exclude(sender=user).count()
    # added 60-62 ai_briefing for weekly brief
    # AI Weekly Insight — returns None on failure so the template hides the card
    ai_briefing = AIService.get_dashboard_briefing(user)

    context = {
        'greeting': greeting,
        'upcoming_events': upcoming_events,
        'recent_notes': recent_notes,
        'deadlines': deadlines,
        'social_posts': social_posts,
        'unread_count': unread_count,
        'ai_briefing': ai_briefing, # added for weekly briefing
        **focus_stats,
    }
    return render(request, 'pages/dashboard.html', context)


@login_required
def profile(request):
    posts = FeedService.get_user_posts(request.user, request.user)
    event, event_status = get_profile_event(request.user)
    friends_count = request.user.following.filter(followers=request.user).count()

    context = {
        'posts': posts,
        'status_choices': User.Status.choices,
        'event': event,
        'event_status': event_status,
        'friends_count': friends_count,
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
