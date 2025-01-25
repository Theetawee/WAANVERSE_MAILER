from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .schema import EmailConfigSchema


@dataclass
class EmailConfig:
    """
    Authentication configuration class that validates and stores all auth-related settings.

    This class provides type checking, validation, and sensible defaults for all
    authentication configuration options.
    """

    def __init__(self, config_dict: EmailConfigSchema):
        self.email_threading_enabled = config_dict.get("EMAIL_THREADING_ENABLED", True)
        self.email_batch_size = config_dict.get("EMAIL_BATCH_SIZE", 50)
        self.email_retry_attempts = config_dict.get("EMAIL_RETRY_ATTEMPTS", 3)
        self.email_retry_delay = config_dict.get("EMAIL_RETRY_DELAY", 5)
        self.email_max_recipients = config_dict.get("EMAIL_MAX_RECIPIENTS", 50)
        self.email_thread_pool_size = config_dict.get("EMAIL_THREAD_POOL_SIZE", 5)
        self.platform_name = config_dict.get("PLATFORM_NAME", "Waanverse")
        self.platform_address = config_dict.get("PLATFORM_ADDRESS", "Waanverse Labs")
        self.platform_contact_email = config_dict.get(
            "PLATFORM_CONTACT_EMAIL", "support@waanverse.com"
        )
        self.unsubscribe_link = config_dict.get(
            "UNSUBSCRIBE_LINK", "https://www.waanverse.com"
        )
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate the complete configuration."""
        self._validate_email_settings()

    @staticmethod
    def _validate_email_settings() -> None:
        """Validate required email settings."""
        required_settings = [
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "EMAIL_USE_TLS",
        ]

        missing_settings = [
            setting
            for setting in required_settings
            if not getattr(settings, setting, None)
        ]

        if missing_settings:
            raise ImproperlyConfigured(
                "Missing required email settings: "
                f"{', '.join(missing_settings)}. "
                "See https://docs.djangoproject.com/en/stable/topics/email/"
            )


EMAIL_CONFIG = getattr(settings, "WAANVERSE_EMAIL_CONFIG", {})
email_config = EmailConfig(EMAIL_CONFIG)
