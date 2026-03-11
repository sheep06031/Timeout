from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from timeout.forms import SignupForm, LoginForm, CompleteProfileForm


def signup_view(request):
    """Handle user registration (email + password only)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(
                request, user,
                backend='django.contrib.auth.backends.ModelBackend'
            )
            request.session['needs_profile_completion'] = True
            messages.success(request, 'Account created! Please complete your profile.')
            return redirect('complete_profile')
    else:
        form = SignupForm()

    return render(request, 'auth/signup.html', {'form': form})


def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(
                request,
                f'Welcome back, {user.username}!'
            )
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')


@login_required
def complete_profile(request):
    """
    Let new users (local and social) fill in missing profile fields.
    Only accessible when the session flag 'needs_profile_completion' is set
    (i.e. right after signup). Existing users logging in are never shown this.
    """
    if not request.session.get('needs_profile_completion'):
        return redirect('dashboard')

    user = request.user

    if request.method == 'POST':
        form = CompleteProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            # Clear the flag so the user isn't shown this page again
            request.session.pop('needs_profile_completion', None)
            messages.success(request, 'Profile completed successfully!')
            return redirect('dashboard')
    else:
        form = CompleteProfileForm(instance=user)

    has_temp_username = user.username.startswith('user_')

    context = {
        'form': form,
        'has_temp_username': has_temp_username,
    }
    return render(request, 'auth/complete_profile.html', context)
