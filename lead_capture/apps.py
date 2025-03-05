from django.apps import AppConfig


class LeadCaptureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lead_capture'

    def ready(self):
        """Connect signal handlers"""
        import lead_capture.signals
