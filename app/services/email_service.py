"""Email service for sending appointment reminder emails using Mailgun"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
import pendulum
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)



class AppointmentEmailData(BaseModel):
    user_name: str
    specialist_name: str
    specialist_type: str
    appointment_datetime: datetime
    appointment_format: str
    meeting_link: str
    company_name: str
    support_email: str
    appointment_id: str
    reminder_minutes: int = 15

class MailgunService:
    """Service for sending emails via Mailgun API with scheduled delivery"""

    def __init__(self):
        self.api_key = settings.MAILGUN_API_KEY
        self.domain = settings.MAILGUN_DOMAIN
        self.base_url = settings.MAILGUN_BASE_URL
        self.webhook_signing_key = settings.MAILGUN_WEBHOOK_SIGNING_KEY
        self.template_name = "15min_before_appointment"  # Match your template name
        
        if not self.api_key or not self.domain:
            logger.warning("Mailgun API key or domain not configured. Email functionality will be disabled.")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Mailgun API requests"""
        return {
            "Authorization": f"Basic api:{self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _get_api_url(self, endpoint: str) -> str:
        """Construct full API URL for endpoint"""
        return urljoin(f"{self.base_url}/{self.domain}/", endpoint)

    def schedule_appointment_reminder(
        self,
        to_email: str,
        appointment_data: AppointmentEmailData,
    ) -> Optional[str]:
        """
        Schedule an appointment reminder email using Mailgun's scheduled delivery.

        Args:
            to_email: Recipient email address
            appointment_data: AppointmentEmailData containing appointment details
            delivery_time: When to deliver the email

        Returns:
            Message ID if successful, None if failed
        """
        if not self.api_key or not self.domain:
            logger.error("Mailgun not configured. Cannot send email.")
            return None

        try:
            url = self._get_api_url("messages")

            
            pendulum_appointment_datetime = pendulum.instance(appointment_data.appointment_datetime)
            delivery_time = pendulum_appointment_datetime.subtract(minutes=appointment_data.reminder_minutes)
            

            # Check if delivery time is in the past
            if delivery_time < pendulum.now():
                logger.warning(f"Delivery time {delivery_time} is in the past. Skipping email scheduling.")
                return None

            # Format delivery time for Mailgun (RFC 2822 format)
            delivery_time_str = delivery_time.to_rfc2822_string()

            # Prepare template variables as JSON
            template_variables = {
                "user_name": appointment_data.user_name,
                "specialist_name": appointment_data.specialist_name,
                "specialist_type": appointment_data.specialist_type,
                "appointment_format": appointment_data.appointment_format,
                "meeting_link": appointment_data.meeting_link,
                "company_name": appointment_data.company_name,
                "support_email": appointment_data.support_email,
                "appointment_id": appointment_data.appointment_id,
            }

            data = {
                "from": f"{appointment_data.company_name} <{settings.EMAIL_FROM}>",
                "to": to_email,
                "subject": f"Your Appointment is Coming Up - {pendulum_appointment_datetime.format('MMMM D, YYYY h:mm A')}",
                "template": self.template_name,
                "o:deliverytime": delivery_time_str,
                "o:tag": ["appointment-reminder", f"appointment-{appointment_data.appointment_id}"],
                "o:tracking": "yes",
                "o:tracking-clicks": "yes",
                "o:tracking-opens": "yes",
                "h:X-Mailgun-Variables": json.dumps(template_variables),
            }

            response = httpx.post(url, headers=self._get_headers(), data=data)
            response.raise_for_status()

            result = response.json()
            message_id = result.get("id")

            logger.info(f"Scheduled appointment reminder email for {to_email}, message ID: {message_id}")
            return message_id

        except httpx.RequestError as e:
            logger.error(f"Failed to schedule appointment reminder email: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error scheduling appointment reminder email: {e.response.status_code} - {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scheduling email: {str(e)}")
            return None

    def cancel_scheduled_email(self, message_id: str) -> bool:
        """
        Cancel a scheduled email using Mailgun's message cancellation.
        Note: This only works for messages that haven't been sent yet.
        
        Args:
            message_id: The Mailgun message ID to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        if not self.api_key or not self.domain or not message_id:
            logger.error("Mailgun not configured or no message ID provided")
            return False

        try:
            # Mailgun doesn't have a direct cancel API, but we can try to delete from queue
            # This is a best-effort approach
            url = self._get_api_url(f"messages/{message_id}")

            response = httpx.delete(url, headers=self._get_headers())

            if response.status_code == 200:
                logger.info(f"Successfully cancelled scheduled email: {message_id}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Message {message_id} not found (may have already been sent)")
                return False
            else:
                logger.error(f"Failed to cancel email {message_id}: {response.status_code}")
                return False

        except httpx.RequestError as e:
            logger.error(f"Failed to cancel scheduled email {message_id}: {str(e)}")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error cancelling scheduled email {message_id}: {e.response.status_code} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error cancelling email {message_id}: {str(e)}")
            return False

    def verify_webhook_signature(self, token: str, timestamp: str, signature: str) -> bool:
        """
        Verify Mailgun webhook signature for security.
        
        Args:
            token: Token from webhook
            timestamp: Timestamp from webhook
            signature: Signature from webhook
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_signing_key:
            logger.warning("Webhook signing key not configured")
            return False

        try:
            # Construct the signing string
            signing_string = f"{timestamp}{token}"
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_signing_key.encode(),
                signing_string.encode(),
                hashlib.sha256
            ).hexdigest()

            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    def send_immediate_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Optional[str]:
        """
        Send an immediate email (for testing or urgent notifications).
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional)
            
        Returns:
            Message ID if successful, None if failed
        """
        if not self.api_key or not self.domain:
            logger.error("Mailgun not configured. Cannot send email.")
            return None

        try:
            url = self._get_api_url("messages")
            
            data = {
                "from": f"Ephra <{settings.EMAIL_FROM}>",
                "to": to_email,
                "subject": subject,
                "html": html_content,
                "o:tracking": "yes",
                "o:tracking-clicks": "yes",
                "o:tracking-opens": "yes",
            }
            
            if text_content:
                data["text"] = text_content

            response = httpx.post(url, headers=self._get_headers(), data=data)
            response.raise_for_status()

            result = response.json()
            message_id = result.get("id")

            logger.info(f"Sent immediate email to {to_email}, message ID: {message_id}")
            return message_id

        except httpx.RequestError as e:
            logger.error(f"Failed to send immediate email: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending immediate email: {e.response.status_code} - {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
            return None

    def get_email_events(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get events for a specific message (delivered, opened, clicked, etc.).
        
        Args:
            message_id: The Mailgun message ID
            
        Returns:
            Dictionary of events if successful, None if failed
        """
        if not self.api_key or not self.domain or not message_id:
            return None

        try:
            url = self._get_api_url("events")
            params = {"message-id": message_id}

            response = httpx.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Failed to get email events for {message_id}: {str(e)}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting email events for {message_id}: {e.response.status_code} - {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting email events: {str(e)}")
            return None

    def is_configured(self) -> bool:
        """Check if Mailgun is properly configured"""
        return bool(self.api_key and self.domain)


# Global instance
mailgun_service = MailgunService()
