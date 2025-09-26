"""Tests for email service functionality"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from app.services.email_service import MailgunService


class TestMailgunService:
    """Test cases for MailgunService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = MailgunService()
        self.service.api_key = "test-api-key"
        self.service.domain = "test.mailgun.org"
        self.service.webhook_signing_key = "test-webhook-key"

    def test_is_configured_true(self):
        """Test is_configured returns True when properly configured"""
        assert self.service.is_configured() is True

    def test_is_configured_false(self):
        """Test is_configured returns False when not configured"""
        service = MailgunService()
        service.api_key = ""
        service.domain = ""
        assert service.is_configured() is False

    @patch('httpx.post')
    def test_schedule_appointment_reminder_success(self, mock_post):
        """Test successful appointment reminder scheduling"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"id": "test-message-id"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        appointment_data = {
            "appointment_id": "test-id",
            "patient_name": "John Doe",
            "provider_name": "Dr. Smith",
            "appointment_date": "January 15, 2024",
            "appointment_time": "2:00 PM",
            "meeting_link": "https://meet.example.com/test"
        }
        delivery_time = datetime.now(timezone.utc) + timedelta(minutes=15)

        result = self.service.schedule_appointment_reminder(
            "test@example.com", appointment_data, delivery_time
        )

        assert result == "test-message-id"
        mock_post.assert_called_once()

    @patch('httpx.post')
    def test_schedule_appointment_reminder_failure(self, mock_post):
        """Test appointment reminder scheduling failure"""
        # Mock failed response
        mock_post.side_effect = httpx.RequestError("API Error")

        appointment_data = {
            "appointment_id": "test-id",
            "patient_name": "John Doe",
            "provider_name": "Dr. Smith"
        }
        delivery_time = datetime.now(timezone.utc) + timedelta(minutes=15)

        result = self.service.schedule_appointment_reminder(
            "test@example.com", appointment_data, delivery_time
        )

        assert result is None

    @patch('httpx.delete')
    def test_cancel_scheduled_email_success(self, mock_delete):
        """Test successful email cancellation"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        result = self.service.cancel_scheduled_email("test-message-id")

        assert result is True
        mock_delete.assert_called_once()

    @patch('httpx.delete')
    def test_cancel_scheduled_email_not_found(self, mock_delete):
        """Test email cancellation when message not found"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        result = self.service.cancel_scheduled_email("test-message-id")

        assert result is False

    def test_verify_webhook_signature_valid(self):
        """Test webhook signature verification with valid signature"""
        import hashlib
        import hmac

        token = "test-token"
        timestamp = "1234567890"
        signing_string = f"{timestamp}{token}"
        expected_signature = hmac.new(
            self.service.webhook_signing_key.encode(),
            signing_string.encode(),
            hashlib.sha256
        ).hexdigest()

        result = self.service.verify_webhook_signature(token, timestamp, expected_signature)

        assert result is True

    def test_verify_webhook_signature_invalid(self):
        """Test webhook signature verification with invalid signature"""
        result = self.service.verify_webhook_signature(
            "test-token", "1234567890", "invalid-signature"
        )

        assert result is False



