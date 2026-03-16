import random
import time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect

from timeout.forms.auth import validate_password_strength
from timeout.services.email_service import EmailService

User = get_user_model()

# Code expiry in seconds (10 minutes)
CODE_EXPIRY = 600


def forgot_password(request):
    """
    Step 1 & 2: User enters email/username, receives a 6-digit code,
    then enters the code on the same page.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    step = request.POST.get('step', 'request')

    if request.method == 'POST' and step == 'request':
        identifier = request.POST.get('identifier', '').strip()
        if not identifier:
            messages.error(request, 'Please enter your email or username.')
            return render(request, 'auth/forgot_password.html', {
                'step': 'request',
                'identifier': identifier,
            })

        # Look up user by email or username
        user = User.objects.filter(email=identifier).first()
        if not user:
            user = User.objects.filter(username=identifier).first()

        if not user:
            messages.error(request, 'No account found with that email or username.')
            return render(request, 'auth/forgot_password.html', {
                'step': 'request',
                'identifier': identifier,
            })

        # Generate 6-digit code
        code = f'{random.randint(0, 999999):06d}'
        request.session['reset_code'] = code
        request.session['reset_user_id'] = user.pk
        request.session['reset_code_time'] = time.time()

        # Send via SendGrid
        sent = EmailService.send_reset_code(user.email, code)
        if not sent:
            messages.error(request, 'Failed to send the reset code. Please try again later.')
            return render(request, 'auth/forgot_password.html', {
                'step': 'request',
                'identifier': identifier,
            })

        # Mask email for display
        email = user.email
        local, domain = email.split('@')
        masked = local[:2] + '***@' + domain
        messages.success(request, f'A 6-digit code has been sent to {masked}.')

        return render(request, 'auth/forgot_password.html', {
            'step': 'verify',
            'masked_email': masked,
        })

    if request.method == 'POST' and step == 'verify':
        entered_code = request.POST.get('code', '').strip()
        stored_code = request.session.get('reset_code')
        code_time = request.session.get('reset_code_time', 0)

        if not stored_code:
            messages.error(request, 'Session expired. Please start over.')
            return render(request, 'auth/forgot_password.html', {'step': 'request'})

        if time.time() - code_time > CODE_EXPIRY:
            # Clear expired session data
            for key in ('reset_code', 'reset_user_id', 'reset_code_time'):
                request.session.pop(key, None)
            messages.error(request, 'Code has expired. Please request a new one.')
            return render(request, 'auth/forgot_password.html', {'step': 'request'})

        if entered_code != stored_code:
            messages.error(request, 'Invalid code. Please try again.')
            return render(request, 'auth/forgot_password.html', {'step': 'verify'})

        # Code verified — mark session and redirect to reset page
        request.session['reset_verified'] = True
        return redirect('reset_password')

    # GET request — show step 1
    return render(request, 'auth/forgot_password.html', {'step': 'request'})


def reset_password(request):
    """
    Step 3: User sets a new password after code verification.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if not request.session.get('reset_verified'):
        messages.error(request, 'Please verify your code first.')
        return redirect('forgot_password')

    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please start over.')
        return redirect('forgot_password')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please start over.')
        return redirect('forgot_password')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/reset_password.html')

        try:
            validate_password_strength(password1)
        except Exception as e:
            messages.error(request, str(e.message))
            return render(request, 'auth/reset_password.html')

        user.set_password(password1)
        user.save()

        # Clear all reset session data
        for key in ('reset_code', 'reset_user_id', 'reset_code_time', 'reset_verified'):
            request.session.pop(key, None)

        messages.success(request, 'Password reset successfully! You can now log in.')
        return redirect('landing')

    return render(request, 'auth/reset_password.html')
