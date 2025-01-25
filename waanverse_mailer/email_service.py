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
    MAX_TOTAL_RECIPIENTS = 100  # Maximum total recipients (To + CC + BCC)


class EmailService:
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

    def _validate_recipients(self, recipient_list: Union[str, List[str]]) -> List[str]:
        """
        Validate and normalize recipient list.

        Args:
            recipient_list: Recipients to validate

        Returns:
            List of valid email addresses
        """
        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        # Remove duplicates and validate
        unique_recipients = list(set(recipient_list))
        valid_recipients = [r for r in unique_recipients if self.validate_email(r)]

        return valid_recipients

    def parallel_email_send(
        self,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        recipient_list: List[str],
        priority: str = "medium",
        attachments: Optional[List[str]] = None,
        cc_list: Optional[List[str]] = None,
        bcc_list: Optional[List[str]] = None,
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
            cc_list: Carbon copy recipients
            bcc_list: Blind carbon copy recipients

        Returns:
            Detailed result of email sending
        """
        valid_recipients = self._validate_recipients(recipient_list)
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
                    True,
                    cc_list,
                    bcc_list,
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

    def send_batch_emails(
        self,
        template_name: str,
        context: dict,
        recipient_list: List[str],
        subject: str,
        priority: str = "medium",
        attachments: Optional[List[str]] = None,
        cc_list: Optional[List[str]] = None,
        bcc_list: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send batch emails using parallel sending method.

        Returns:
            Dictionary with email sending results
        """
        # Prepare batches of recipients
        batched_recipients = [
            recipient_list[i : i + self.config.BATCH_SIZE]
            for i in range(0, len(recipient_list), self.config.BATCH_SIZE)
        ]

        total_results = {
            "total_recipients": len(recipient_list),
            "successful_sends": 0,
            "failed_sends": 0,
            "failed_recipients": [],
        }

        # Process each batch in parallel
        for batch in batched_recipients:
            batch_results = self.parallel_email_send(
                subject=subject,
                template_name=template_name,
                context=context,
                recipient_list=batch,
                priority=priority,
                attachments=attachments,
                cc_list=cc_list,
                bcc_list=bcc_list,
            )

            # Aggregate results
            total_results["successful_sends"] += batch_results["successful_sends"]
            total_results["failed_sends"] += batch_results["failed_sends"]
            total_results["failed_recipients"].extend(
                batch_results["failed_recipients"]
            )

        return total_results

    def retry_failed_emails(
        self, failed_recipients: List[dict], retries: int = 3, delay: int = 5
    ):
        """
        Retry sending emails for failed recipients.

        Args:
            failed_recipients: List of failed recipient dictionaries
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.
        """
        for attempt in range(1, retries + 1):
            for failed in failed_recipients[:]:  # Iterate over a copy
                try:
                    email_message = self.prepare_email_message(
                        subject=failed.get("subject", "Retry Email"),
                        template_name=failed.get("template_name", "default"),
                        context=failed.get("context", {}),
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

    def prepare_email_message(
        self,
        subject: str,
        template_name: str,
        context: dict,
        recipient_list: Union[str, List[str]],
        priority: str = "medium",
        attachments: Optional[List] = None,
        cc_list: Optional[Union[str, List[str]]] = None,
        bcc_list: Optional[Union[str, List[str]]] = None,
    ) -> EmailMultiAlternatives:
        """
        Prepare an email message with comprehensive recipient support.

        Args:
            subject: Email subject
            template_name: Name of the template
            context: Context data for the template
            recipient_list: Primary recipients
            priority: Email priority level
            attachments: List of attachment files
            cc_list: Carbon copy recipients
            bcc_list: Blind carbon copy recipients

        Returns:
            Prepared email message
        """
        # Validate and normalize recipient lists
        to_recipients = self._validate_recipients(recipient_list)
        cc_recipients = self._validate_recipients(cc_list) if cc_list else []
        bcc_recipients = self._validate_recipients(bcc_list) if bcc_list else []

        # Check total recipient count
        total_recipients = len(to_recipients) + len(cc_recipients) + len(bcc_recipients)
        if total_recipients > self.config.MAX_TOTAL_RECIPIENTS:
            raise ValueError(
                f"Too many recipients (max {self.config.MAX_TOTAL_RECIPIENTS})"
            )

        template_path = f"emails/{template_name}.html"

        # Update context with standard platform information
        context.update(
            {
                "site_name": email_config.platform_name,
                "company_address": email_config.platform_address,
                "support_email": email_config.platform_contact_email,
                "unsubscribe_link": email_config.unsubscribe_link,
            }
        )

        # Render email content
        html_content = render_to_string(template_path, context)
        plain_content = strip_tags(html_content)

        # Create email message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_recipients,
            cc=cc_recipients,
            bcc=bcc_recipients,
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
        cc_list: Optional[Union[str, List[str]]] = None,
        bcc_list: Optional[Union[str, List[str]]] = None,
    ) -> bool:
        """
        Send an email with comprehensive recipient and threading support.

        Args:
            subject: Email subject
            template_name: Template name
            context: Template context
            recipient_list: Primary recipients
            priority: Email priority
            attachments: Email attachments
            async_send: Whether to send asynchronously
            cc_list: Carbon copy recipients
            bcc_list: Blind carbon copy recipients

        Returns:
            bool: Whether the email was sent successfully
        """
        try:
            # Prepare email message with all recipient types
            email_message = self.prepare_email_message(
                subject,
                template_name,
                context,
                recipient_list,
                priority,
                attachments,
                cc_list,
                bcc_list,
            )

            # Send email
            if async_send and email_config.email_threading_enabled:
                self.EmailThread(self, [email_message]).start()
            else:
                email_message.send()

            # Log successful send
            total_recipients = (
                len(recipient_list)
                + (len(cc_list) if cc_list else 0)
                + (len(bcc_list) if bcc_list else 0)
            )
            logger.info(
                f"Email sent successfully to {total_recipients} recipients: {subject}"
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
