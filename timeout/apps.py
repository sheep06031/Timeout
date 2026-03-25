from django.apps import AppConfig


class TimeoutConfig(AppConfig):
    """Django app configuration for the timeout application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timeout'

    def ready(self):
        """Initialize app by registering signal handlers."""
        import timeout.signals
