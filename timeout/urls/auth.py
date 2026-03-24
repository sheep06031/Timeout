from django.urls import path
from timeout.views import auth
from timeout.views import password_reset

""" Authentication related URL patterns for the timeout app. """

urlpatterns = [
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('complete-profile/', auth.complete_profile, name='complete_profile'),
    path('forgot-password/', password_reset.forgot_password, name='forgot_password'),
    path('reset-password/', password_reset.reset_password, name='reset_password'),
]
