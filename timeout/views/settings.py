import json

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from timeout.forms import AppearanceForm


def _handle_settings_post(request, user):
    """Process POST actions on the settings page. Returns a redirect or updated password_form."""
    action = request.POST.get('action', '')
    if action == 'password':
        password_form = PasswordChangeForm(user, request.POST)
        if password_form.is_valid():
            u = password_form.save()
            update_session_auth_hash(request, u)
            messages.success(request, 'Password changed successfully!')
            return redirect('settings')
        messages.error(request, 'Please fix the errors below.')
        return password_form
    if action == 'delete_account':
        user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('landing')
    return None


@login_required
def settings_view(request):
    """Settings page with appearance, pomodoro, and account sections."""
    user = request.user
    appearance_form = AppearanceForm(instance=user)
    password_form = PasswordChangeForm(user)
    if request.method == 'POST':
        result = _handle_settings_post(request, user)
        if isinstance(result, PasswordChangeForm):
            password_form = result
        elif result is not None:
            return result
    context = {
        'appearance_form': appearance_form,
        'password_form': password_form}
    return render(request, 'pages/settings.html', context)


@login_required
@require_POST
def settings_save_ajax(request):
    """AJAX endpoint, auto-save appearance/pomodoro/notes settings."""
    form = AppearanceForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
