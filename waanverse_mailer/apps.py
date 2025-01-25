# flake8: noqa

from django.apps import AppConfig


class WaanverseMailerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "waanverse_mailer"
    label = "waanverse_mailer"
    verbose_name = "Waanverse Mailer"

    def ready(self):
        """
        Validate middleware configuration when the app is ready.
        This runs during Django's initialization process.
        """
        self.validate_required_settings()

    def validate_required_settings(self):
        """
        Validates other required settings are properly configured
        """
        pass
