"""
Study planner URL patterns for the timeout app.
Includes:
- plan_sessions: View to display the study planner interface and generate AI session suggestions based on upcoming deadlines.
- confirm_sessions: View to receive confirmed session times from the frontend and create Event instances for the study sessions.
"""
from django.urls import path
from timeout.views import study_planner


urlpatterns = [
    path('plan/', study_planner.plan_sessions, name='study_planner_plan'),
    path('confirm/', study_planner.confirm_sessions, name='study_planner_confirm'),
]
