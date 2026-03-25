from django.apps import AppConfig


class TimeoutConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'timeout'

    def ready(self):
        """Import signal handlers to ensure they are registered."""
        import timeout.signals
