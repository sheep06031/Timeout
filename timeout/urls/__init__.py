from django.urls import path, include

urlpatterns = [
    path('', include('timeout.urls.auth')),
    path('', include('timeout.urls.pages')),
    path('social/', include('timeout.urls.social')),
    path('', include('timeout.urls.calendar')),
    path('messaging/', include('timeout.urls.messaging')),
    path('notes/', include('timeout.urls.notes')),
    path('study-planner/', include('timeout.urls.study_planner')),
]
