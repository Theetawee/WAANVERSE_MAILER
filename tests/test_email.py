from unittest.mock import patch

from django.test import TestCase, override_settings

from waanverse_mailer.email_service import EnhancedEmailService


class EmailServiceTestCase(TestCase):
    def setUp(self):
        self.email_service = EnhancedEmailService()
        self.test_recipient = "test@example.com"
        self.test_context = {
            "username": "TestUser",
            "verification_link": "http://test.com/verify",
        }

    def test_email_validation(self):
        """Test email validation method."""
        valid_emails = [
            "user@example.com",
            "john.doe@company.co.uk",
            "user+tag@example.com",
        ]
        invalid_emails = ["invalid-email", "missing@domain", "@missinglocal.com", ""]

        for email in valid_emails:
            self.assertTrue(
                self.email_service.validate_email(email),
                f"Failed to validate valid email: {email}",
            )

        for email in invalid_emails:
            self.assertFalse(
                self.email_service.validate_email(email),
                f"Incorrectly validated invalid email: {email}",
            )

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_send_email_success(self, mock_send):
        """Test successful email sending."""
        mock_send.return_value = 1
        result = self.email_service.send_email(
            subject="Test Email",
            template_name="welcome_email",
            context=self.test_context,
            recipient_list=self.test_recipient,
        )
        self.assertTrue(result)
        mock_send.assert_called_once()

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_send_email_failure(self, mock_send):
        """Test email sending failure handling."""
        mock_send.side_effect = Exception("SMTP Connection Error")
        result = self.email_service.send_email(
            subject="Test Email",
            template_name="welcome_email",
            context=self.test_context,
            recipient_list=self.test_recipient,
        )
        self.assertFalse(result)

    def test_parallel_email_send(self):
        """Test parallel email sending."""
        recipients = ["user1@example.com", "user2@example.com", "invalid-email"]

        with patch.object(self.email_service, "send_email", return_value=True):
            results = self.email_service.parallel_email_send(
                subject="Parallel Test",
                template_name="test_template",
                context=self.test_context,
                recipient_list=recipients,
            )

        self.assertEqual(results["total_recipients"], 3)
        self.assertEqual(results["valid_recipients"], 2)
        self.assertEqual(results["successful_sends"], 2)
        self.assertEqual(results["failed_sends"], 1)

    def test_transactional_email(self):
        """Test transactional email sending."""
        events = ["welcome", "password_reset", "account_verification"]
        for event in events:
            with patch.object(
                self.email_service, "send_email", return_value=True
            ) as mock_send:
                result = self.email_service.send_transactional_email(
                    recipient=self.test_recipient,
                    event_type=event,
                    context=self.test_context,
                )
                self.assertTrue(result)
                mock_send.assert_called_once()

    @override_settings(EMAIL_HOST_USER=None)
    def test_connection_failure(self):
        """Test email connection failure."""
        with self.assertRaises(Exception):
            _ = self.email_service.connection

    def test_max_recipients_limit(self):
        """Test handling of recipient limit."""
        large_recipient_list = [f"user{i}@example.com" for i in range(100)]

        with self.assertRaises(ValueError):
            self.email_service.send_email(
                subject="Large Recipient Test",
                template_name="test_template",
                context=self.test_context,
                recipient_list=large_recipient_list,
            )


@patch("logging.error")
class EmailLoggingTestCase(TestCase):
    """Tests specifically for logging behavior."""

    def setUp(self):
        self.email_service = EnhancedEmailService()

    def test_logging_on_email_failure(self, mock_log_error):
        """Ensure failures are logged."""
        with patch.object(
            self.email_service, "send_email", side_effect=Exception("Test Error")
        ):
            self.email_service.send_email(
                subject="Logging Test",
                template_name="test_template",
                context={},
                recipient_list="test@example.com",
            )

        mock_log_error.assert_called_once()
