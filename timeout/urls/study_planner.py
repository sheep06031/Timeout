"""
Study planner URL patterns for the timeout app.
"""

from django.urls import path
from timeout.views import study_planner


urlpatterns = [
    path('plan/', study_planner.plan_sessions, name='study_planner_plan'),
    path('confirm/', study_planner.confirm_sessions, name='study_planner_confirm'),
]
