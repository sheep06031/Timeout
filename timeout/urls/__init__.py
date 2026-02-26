from django.urls import path, include

urlpatterns = [
    path('', include('timeout.urls.auth')),
    path('', include('timeout.urls.pages')),
    path('social/', include('timeout.urls.social')),
    path('', include('timeout.urls.calendar')),
]
