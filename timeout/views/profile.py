from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timedelta
from timeout.models import Event
from timeout.forms import ProfileEditForm


def get_profile_event(user):
    """Return the most relevant event: current → upcoming → recent."""
    now = timezone.now()
    two_hours = timedelta(hours=2)

    event = Event.objects.filter(
        creator=user,
        start_datetime__lte=now,
        end_datetime__gte=now,
    ).first()
    if event:
        return event, 'active'

    event = Event.objects.filter(
        creator=user,
        start_datetime__gt=now,
        start_datetime__lte=now + two_hours,
    ).order_by('start_datetime').first()
    if event:
        return event, 'upcoming'

    event = Event.objects.filter(
        creator=user,
        end_datetime__lt=now,
        end_datetime__gte=now - two_hours,
    ).order_by('-end_datetime').first()
    if event:
        return event, 'recent'

    return None, None


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, 'pages/profile_edit.html', {'form': form})