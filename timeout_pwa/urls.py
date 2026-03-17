"""
URL configuration for timeout_pwa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from allauth.socialaccount.views import SignupView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Override allauth's socialaccount signup to use our custom template
    path(
        'accounts/social/signup/',
        SignupView.as_view(template_name='auth/google_signin.html'),
        name='socialaccount_signup',
    ),
    path('accounts/', include('allauth.urls')),
    path('', include('timeout.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
