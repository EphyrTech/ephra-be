"""Tests for email service with pendulum integration"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import pendulum

from app.services.email_service import MailgunService, AppointmentEmailData


class TestEmailServicePendulum:
    """Test email service with pendulum datetime handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = MailgunService()
        self.service.api_key = "test-api-key"
        self.service.domain = "test.mailgun.org"
        self.service.webhook_signing_key = "test-webhook-key"

    def test_appointment_email_data_model(self):
        """Test AppointmentEmailData model creation"""
        appointment_time = pendulum.now().add(hours=1)
        
        email_data = AppointmentEmailData(
            user_name="John Doe",
            specialist_name="Dr. Smith",
            specialist_type="Mental Health",
            appointment_date="January 15, 2024",
            appointment_time=appointment_time.isoformat(),
            appointment_format="Video Call",
            meeting_link="https://meet.example.com/test",
            company_name="Ephyr Health",
            support_email="support@ephyr.com",
            appointment_id="test-123",
            reminder_minutes=15
        )
        
        assert email_data.user_name == "John Doe"
        assert email_data.specialist_name == "Dr. Smith"
        assert email_data.reminder_minutes == 15

    @patch('httpx.post')
    def test_schedule_appointment_reminder_with_pendulum(self, mock_post):
        """Test scheduling appointment reminder with pendulum datetime"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"id": "test-message-id"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Create appointment data with future time
        appointment_time = pendulum.now().add(hours=1)
        email_data = AppointmentEmailData(
            user_name="John Doe",
            specialist_name="Dr. Smith",
            specialist_type="Mental Health",
            appointment_date="January 15, 2024",
            appointment_time=appointment_time.isoformat(),
            appointment_format="Video Call",
            meeting_link="https://meet.example.com/test",
            company_name="Ephyr Health",
            support_email="support@ephyr.com",
            appointment_id="test-123",
            reminder_minutes=15
        )

        result = self.service.schedule_appointment_reminder(
            "test@example.com", email_data
        )

        assert result == "test-message-id"
        mock_post.assert_called_once()
        
        # Verify the call was made with proper data
        call_args = mock_post.call_args
        data = call_args[1]['data']
        assert 'o:deliverytime' in data
        assert 'h:X-Mailgun-Variables' in data

    @patch('httpx.post')
    def test_schedule_appointment_reminder_past_time(self, mock_post):
        """Test that emails are not scheduled for past times"""
        # Create appointment data with past time
        appointment_time = pendulum.now().subtract(hours=1)
        email_data = AppointmentEmailData(
            user_name="John Doe",
            specialist_name="Dr. Smith",
            specialist_type="Mental Health",
            appointment_date="January 15, 2024",
            appointment_time=appointment_time.isoformat(),
            appointment_format="Video Call",
            meeting_link="https://meet.example.com/test",
            company_name="Ephyr Health",
            support_email="support@ephyr.com",
            appointment_id="test-123",
            reminder_minutes=15
        )

        result = self.service.schedule_appointment_reminder(
            "test@example.com", email_data
        )

        # Should return None for past delivery times
        assert result is None
        # Should not make HTTP call
        mock_post.assert_not_called()

    def test_pendulum_time_formatting(self):
        """Test that pendulum properly formats times for email template"""
        appointment_time = pendulum.parse("2024-01-15T14:30:00Z")
        
        # Test that pendulum can format the time properly
        formatted_time = appointment_time.format("h:mm A") if hasattr(appointment_time, 'format') else str(appointment_time)
        
        # Should be able to format or convert to string
        assert isinstance(formatted_time, str)
        assert len(formatted_time) > 0

    def test_delivery_time_calculation(self):
        """Test delivery time calculation with pendulum"""
        appointment_time = pendulum.parse("2024-01-15T14:30:00Z")
        reminder_minutes = 15
        
        delivery_time = appointment_time.subtract(minutes=reminder_minutes)
        
        assert delivery_time < appointment_time
        assert (appointment_time - delivery_time).total_seconds() == 15 * 60

    def test_rfc2822_formatting(self):
        """Test RFC 2822 formatting for Mailgun"""
        appointment_time = pendulum.parse("2024-01-15T14:30:00Z")
        delivery_time = appointment_time.subtract(minutes=15)
        
        rfc2822_string = delivery_time.to_rfc2822_string()
        
        # Should be a valid RFC 2822 string
        assert isinstance(rfc2822_string, str)
        assert "GMT" in rfc2822_string or "+0000" in rfc2822_string

    @patch('httpx.post')
    def test_template_variables_structure(self, mock_post):
        """Test that template variables are properly structured"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"id": "test-message-id"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        appointment_time = pendulum.now().add(hours=1)
        email_data = AppointmentEmailData(
            user_name="John Doe",
            specialist_name="Dr. Smith",
            specialist_type="Mental Health",
            appointment_date="January 15, 2024",
            appointment_time=appointment_time.isoformat(),
            appointment_format="Video Call",
            meeting_link="https://meet.example.com/test",
            company_name="Ephyr Health",
            support_email="support@ephyr.com",
            appointment_id="test-123",
            reminder_minutes=15
        )

        self.service.schedule_appointment_reminder("test@example.com", email_data)

        # Verify template variables are properly formatted
        call_args = mock_post.call_args
        data = call_args[1]['data']
        
        import json
        template_vars = json.loads(data['h:X-Mailgun-Variables'])
        
        assert template_vars['user_name'] == "John Doe"
        assert template_vars['specialist_name'] == "Dr. Smith"
        assert template_vars['company_name'] == "Ephyr Health"
        assert template_vars['appointment_id'] == "test-123"
        assert 'appointment_time' in template_vars
