"""Authentication related URL patterns for the timeout app.
Includes:
- signup: View to handle user registration.
- login: View to handle user login.
- logout: View to handle user logout.
- complete_profile: View to handle additional profile information after signup.
- forgot_password: View to handle password reset requests.
- reset_password: View to handle setting a new password after receiving a reset link.
"""

from django.urls import path
from timeout.views import auth
from timeout.views import password_reset

urlpatterns = [
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('complete-profile/', auth.complete_profile, name='complete_profile'),
    path('forgot-password/', password_reset.forgot_password, name='forgot_password'),
    path('reset-password/', password_reset.reset_password, name='reset_password'),
]
