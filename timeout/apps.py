"""
apps.py - Application configuration for the Timeout Django app.
Registers the app and imports signal handlers on startup.
"""

from django.apps import AppConfig

class TimeoutConfig(AppConfig):
    """Django AppConfig for the Timeout application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timeout'

    def ready(self):
        """Import signal handlers to ensure they are registered."""
