# flake8: noqa
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.validators import EmailValidator
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from waanverse_mailer.config.settings import email_config

logger = logging.getLogger(__name__)

Account = get_user_model()


@dataclass
class EmailConfig:
    """Enhanced configuration settings for emails."""

    BATCH_SIZE = email_config.email_batch_size
    RETRY_ATTEMPTS = email_config.email_retry_attempts
    RETRY_DELAY = email_config.email_retry_delay
    MAX_RECIPIENTS = email_config.email_max_recipients
    THREAD_POOL_SIZE = email_config.email_thread_pool_size
    MAX_EMAIL_BODY_SIZE = 10 * 1024 * 1024  # 10 MB limit
    TIMEOUT = 30  # Email connection timeout in seconds


class EnhancedEmailService:
    """Advanced email service with comprehensive error handling and features."""

    def __init__(self, request=None):
        self.config = EmailConfig()
        self.email_validator = EmailValidator()
        self._connection = None
        self.request = request

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Comprehensive email validation with additional checks.

        Args:
            email: Email address to validate

        Returns:
            Boolean indicating email validity
        """
        if not email:
            return False

        # RFC 5322 Official Standard
        email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        try:
            return bool(
                email_regex.match(email)
                and len(email) <= 254  # Total email length
                and len(email.split("@")[0]) <= 64  # Local part length
            )
        except Exception:
            return False

    @property
    def connection(self):
        """Lazy connection with timeout and retry mechanism."""
        if self._connection is None:
            try:
                self._connection = get_connection(
                    username=settings.EMAIL_HOST_USER,
                    password=settings.EMAIL_HOST_PASSWORD,
                    fail_silently=False,
                    timeout=self.config.TIMEOUT,
                )
            except Exception as e:
                logger.error(f"Email connection failed: {e}")
                raise

        return self._connection

    def parallel_email_send(
        self,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        recipient_list: List[str],
        priority: str = "medium",
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send emails in parallel with detailed tracking.

        Args:
            subject: Email subject
            template_name: Template name
            context: Email context
            recipient_list: List of recipients
            priority: Email priority
            attachments: List of attachment paths

        Returns:
            Detailed result of email sending
        """
        valid_recipients = [r for r in recipient_list if self.validate_email(r)]
        results = {
            "total_recipients": len(recipient_list),
            "valid_recipients": len(valid_recipients),
            "successful_sends": 0,
            "failed_sends": 0,
            "failed_recipients": [],
        }

        with ThreadPoolExecutor(max_workers=self.config.THREAD_POOL_SIZE) as executor:
            future_to_recipient = {
                executor.submit(
                    self.send_email,
                    subject,
                    template_name,
                    context,
                    [recipient],
                    priority,
                    attachments,
                ): recipient
                for recipient in valid_recipients
            }

            for future in as_completed(future_to_recipient):
                recipient = future_to_recipient[future]
                try:
                    result = future.result()
                    if result:
                        results["successful_sends"] += 1
                    else:
                        results["failed_sends"] += 1
                        results["failed_recipients"].append(recipient)
                except Exception as e:
                    results["failed_sends"] += 1
                    results["failed_recipients"].append(recipient)
                    logger.error(f"Unexpected error sending to {recipient}: {e}")

        return results

    def send_transactional_email(
        self, recipient: str, event_type: str, context: Dict[str, Any]
    ) -> bool:
        """
        Send transactional emails with event-specific templates.

        Args:
            recipient: Email recipient
            event_type: Type of transactional event
            context: Event-specific context

        Returns:
            Whether email was sent successfully
        """
        try:
            templates = {
                "welcome": "welcome_email",
                "password_reset": "password_reset",
                "account_verification": "account_verification",
                # Add more transactional templates
            }

            template = templates.get(event_type)
            if not template:
                logger.error(f"Unknown transactional email type: {event_type}")
                return False

            subject = f"Waanverse - {event_type.replace('_', ' ').title()}"

            return self.send_email(
                subject=subject,
                template_name=template,
                context=context,
                recipient_list=recipient,
            )
        except Exception as e:
            logger.error(f"Transactional email failed: {e}")
            return False

    class EmailThread(threading.Thread):
        """Thread for asynchronous email sending."""

        def __init__(self, service_instance, emails):
            self.service = service_instance
            self.emails = emails
            super().__init__()

        def run(self):
            """Execute email sending in thread."""
            try:
                with self.service.connection as connection:
                    connection.send_messages(self.emails)
            except Exception as e:
                logger.error(f"Thread email sending failed: {str(e)}")

    def prepare_email_message(
        self,
        subject: str,
        template_name: str,
        context: dict,
        recipient_list: Union[str, List[str]],
        priority: str = "medium",
        attachments: Optional[List] = None,
    ) -> EmailMultiAlternatives:
        """
        Prepare an email message with both HTML and plain text versions.

        Args:
            subject: Email subject
            template_name: Name of the template or EmailTemplate enum
            context: Context data for the template
            recipient_list: List of recipient email addresses
            priority: Email priority level
            attachments: List of attachment files

        Returns:
            Prepared email message
        """
        template_path = f"emails/{template_name}.html"

        context.update(
            {
                "site_name": email_config.platform_name,
                "company_address": email_config.platform_address,
                "support_email": email_config.platform_contact_email,
                "unsubscribe_link": email_config.unsubscribe_link,
            }
        )

        html_content = render_to_string(template_path, context)
        plain_content = strip_tags(html_content)

        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
            connection=self.connection,
        )

        # Add HTML alternative
        msg.attach_alternative(html_content, "text/html")

        # Add attachments
        if attachments:
            for attachment in attachments:
                msg.attach_file(attachment)

        # Set priority headers
        if priority == "high":
            msg.extra_headers["X-Priority"] = "1"

        return msg

    def send_email(
        self,
        subject: str,
        template_name: str,
        context: dict,
        recipient_list: Union[str, List[str]],
        priority: str = "medium",
        attachments: Optional[List] = None,
        async_send: bool = True,
    ) -> bool:
        """
        Send an email with proper error handling and logging.

        Args:
            subject: Email subject
            template_name: Template name or EmailTemplate enum
                The template name should be without the .html extension found in the base folder template folder this will resolve to emails/{template_name}.html
            context: Template context
            recipient_list: Recipients
                Can be a string or a list of strings
            priority: Email priority
                EmailPriority.HIGH, MEDIUM, LOW
            attachments: Email attachments
            async_send: Whether to send asynchronously
        The following context variables are available:
            site_name: Platform name
            company_address: Platform address
            support_email: Platform support email
        Returns:
            bool: Whether the email was sent successfully
        """
        try:
            # Validate recipients
            if isinstance(recipient_list, str):
                recipient_list = [recipient_list]

            if len(recipient_list) > self.config.MAX_RECIPIENTS:
                raise ValueError(
                    f"Too many recipients (max {self.config.MAX_RECIPIENTS})"
                )

            # Prepare email message
            email_message = self.prepare_email_message(
                subject, template_name, context, recipient_list, priority, attachments
            )

            # Send email
            if async_send and email_config.email_threading_enabled:
                self.EmailThread(self, [email_message]).start()
            else:
                email_message.send()

            logger.info(
                f"Email sent successfully to {len(recipient_list)} recipients: {subject}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send email: {str(e)}",
                extra={
                    "subject": subject,
                    "template": template_name,
                    "recipients": len(recipient_list),
                },
                exc_info=True,
            )
            return False

    def send_batch_emails(
        self,
        template_name: str,
        context: dict,
        recipient_list: List[str],
        subject: str,
    ) -> tuple[int, int, List[dict]]:
        """
        Send batch emails with logging of failed recipients.

        Returns:
            tuple: (success_count, failure_count, failed_recipients)
        """
        success_count = 0
        failure_count = 0
        failed_recipients = []

        for i in range(0, len(recipient_list), self.config.BATCH_SIZE):
            batch = recipient_list[i : i + self.config.BATCH_SIZE]
            messages = [
                self.prepare_email_message(subject, template_name, context, [recipient])
                for recipient in batch
            ]

            try:
                with self.connection as connection:
                    connection.send_messages(messages)
                success_count += len(batch)
            except Exception as e:
                logger.error(f"Batch email sending failed for {batch}: {str(e)}")
                failure_count += len(batch)
                # Log individual failures
                failed_recipients.extend(
                    {"recipient": recipient, "error": str(e)} for recipient in batch
                )

        return success_count, failure_count, failed_recipients

    def retry_failed_emails(
        self, failed_recipients: List[dict], retries: int = 3, delay: int = 5
    ):
        """
        Retry sending emails for failed recipients.

        Args:
            failed_recipients: List of failed recipient dictionaries with `recipient` and `error` keys.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.
        """
        for attempt in range(1, retries + 1):
            for failed in failed_recipients[
                :
            ]:  # Iterate over a copy to modify the list
                try:
                    email_message = self.prepare_email_message(
                        subject=failed["subject"],
                        template_name=failed["template_name"],
                        context=failed["context"],
                        recipient_list=[failed["recipient"]],
                    )
                    email_message.send()
                    failed_recipients.remove(failed)  # Remove if successful
                    logger.info(
                        f"Retried email sent successfully to {failed['recipient']}"
                    )
                except Exception as e:
                    logger.error(
                        f"Retry {attempt}/{retries} failed for {failed['recipient']}: {str(e)}"
                    )
            if failed_recipients:
                time.sleep(delay)
