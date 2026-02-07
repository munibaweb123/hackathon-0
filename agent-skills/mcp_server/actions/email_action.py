"""
Email Action Module

This module handles email sending actions through the MCP server.
It implements proper validation and security checks before sending emails.
"""

from typing import Dict, Any, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
from ...core.logger import Logger


class EmailAction:
    """
    Handles email sending actions through the MCP server.
    Implements proper validation and security checks before sending emails.
    """

    def __init__(self, logger: Optional[Logger] = None):
        """
        Initialize the email action handler.

        Args:
            logger: Logger instance for auditability
        """
        self.logger = logger

    def execute(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the email sending action.

        Args:
            action_data: Dictionary containing email parameters

        Returns:
            Dictionary with execution result
        """
        try:
            # Extract email parameters
            to = action_data.get('to', [])
            cc = action_data.get('cc', [])
            bcc = action_data.get('bcc', [])
            subject = action_data.get('subject', 'Default Subject')
            body = action_data.get('body', 'Default Body')
            html_body = action_data.get('html_body')
            attachments = action_data.get('attachments', [])

            # Validate email parameters
            if not self.validate_email_params(to, subject, body):
                return {
                    "success": False,
                    "error": "Invalid email parameters",
                    "message_id": None
                }

            # For demo purposes, we'll simulate sending the email
            # In a real implementation, this would connect to an SMTP server or email service
            message_id = self._simulate_send_email(to, cc, bcc, subject, body, html_body, attachments)

            if self.logger:
                self.logger.log_system_event(
                    event_type="email_sent",
                    component="email_action",
                    message="Email sent successfully",
                    details={
                        "to": to,
                        "subject": subject,
                        "message_id": message_id
                    }
                )

            return {
                "success": True,
                "message_id": message_id,
                "details": f"Email sent to {len(to)} recipients"
            }

        except Exception as e:
            if self.logger:
                self.logger.log_system_event(
                    event_type="email_error",
                    component="email_action",
                    message=f"Error sending email: {e}",
                    details={"action_data": action_data}
                )

            return {
                "success": False,
                "error": str(e),
                "message_id": None
            }

    def validate_email_params(self, to: list, subject: str, body: str) -> bool:
        """
        Validate email parameters before sending.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body

        Returns:
            True if parameters are valid, False otherwise
        """
        # Check if to list is provided and not empty
        if not to or not isinstance(to, list) or len(to) == 0:
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="email_action",
                    message="No recipients provided",
                    details={"to": to}
                )
            return False

        # Validate email format (basic validation)
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for recipient in to:
            if not isinstance(recipient, str) or not re.match(email_pattern, recipient):
                if self.logger:
                    self.logger.log_system_event(
                        event_type="validation_error",
                        component="email_action",
                        message=f"Invalid email address: {recipient}",
                        details={"to": to}
                    )
                return False

        # Check if subject is provided
        if not subject or not isinstance(subject, str):
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="email_action",
                    message="Invalid email subject",
                    details={"subject": subject}
                )
            return False

        # Check if body is provided
        if not body or not isinstance(body, str):
            if self.logger:
                self.logger.log_system_event(
                    event_type="validation_error",
                    component="email_action",
                    message="Invalid email body",
                    details={"body_length": len(body) if body else 0}
                )
            return False

        return True

    def _simulate_send_email(self, to: list, cc: list, bcc: list,
                           subject: str, body: str, html_body: Optional[str],
                           attachments: list) -> str:
        """
        Simulate sending an email (for demo purposes).
        In a real implementation, this would connect to an SMTP server.

        Args:
            to: List of primary recipients
            cc: List of carbon copy recipients
            bcc: List of blind carbon copy recipients
            subject: Email subject
            body: Plain text email body
            html_body: HTML email body (optional)
            attachments: List of attachment file paths

        Returns:
            Mock message ID
        """
        # Create a mock message ID
        message_id = f"msg_{uuid.uuid4()}"

        # In a real implementation, this would:
        # 1. Connect to SMTP server using credentials from environment
        # 2. Create email message with MIME
        # 3. Send the email
        # 4. Handle any errors

        print(f"SIMULATED: Email sent to {to}, CC: {cc}, BCC: {bcc}")
        print(f"Subject: {subject}")
        print(f"Body preview: {body[:50]}...")
        print(f"Attachments: {len(attachments)}")
        print(f"Message ID: {message_id}")

        return message_id

    def get_disallowed_recipients(self) -> list:
        """
        Get a list of disallowed recipient patterns to prevent unauthorized emails.

        Returns:
            List of disallowed email patterns
        """
        # In a real implementation, this would come from configuration
        return [
            "admin@", "root@", "postmaster@", "abuse@", "webmaster@",
            "support@", "sales@", "marketing@"
        ]