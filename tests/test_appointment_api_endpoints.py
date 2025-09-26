"""Tests for appointment API endpoints with email functionality"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User, UserRole, Appointment, AppointmentStatus
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule


class TestAppointmentAPIEndpoints:
    """Test appointment API endpoints"""

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.role = UserRole.USER
        return user

    @pytest.fixture
    def mock_appointment(self):
        """Mock appointment"""
        appointment = Mock(spec=Appointment)
        appointment.id = "appointment-123"
        appointment.user_id = "user-123"
        appointment.care_provider_id = "provider-123"
        appointment.start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        appointment.end_time = datetime.now(timezone.utc) + timedelta(hours=2)
        appointment.status = AppointmentStatus.PENDING
        appointment.meeting_link = "https://meet.example.com/test"
        appointment.reminder_minutes = 15
        appointment.email_message_id = "message-123"
        appointment.email_scheduled = True
        appointment.email_delivered = False
        appointment.email_opened = False
        appointment.created_at = datetime.now(timezone.utc)
        appointment.updated_at = None
        return appointment

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_create_appointment_success(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user, mock_appointment):
        """Test successful appointment creation with email scheduling"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.create_appointment.return_value = mock_appointment
        mock_service_class.return_value = mock_service

        # Test data
        appointment_data = {
            "care_provider_id": "provider-123",
            "start_time": "2024-01-15T14:00:00Z",
            "end_time": "2024-01-15T15:00:00Z",
            "user_id": "user-123",
            "reminder_minutes": 15
        }

        # Make request
        response = client.post("/v1/appointments/", json=appointment_data)

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "appointment-123"
        assert data["email_scheduled"] is True
        assert data["reminder_minutes"] == 15

        # Verify service was called
        mock_service.create_appointment.assert_called_once()

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_reschedule_appointment_success(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user, mock_appointment):
        """Test successful appointment rescheduling"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.reschedule_appointment.return_value = mock_appointment
        mock_service_class.return_value = mock_service

        # Test data
        reschedule_data = {
            "start_time": "2024-01-15T16:00:00Z",
            "end_time": "2024-01-15T17:00:00Z",
            "reminder_minutes": 30
        }

        # Make request
        response = client.put("/v1/appointments/appointment-123/reschedule", json=reschedule_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "appointment-123"

        # Verify service was called
        mock_service.reschedule_appointment.assert_called_once()
        call_args = mock_service.reschedule_appointment.call_args
        assert call_args[0][0] == "appointment-123"  # appointment_id
        assert isinstance(call_args[0][1], AppointmentReschedule)  # reschedule_data
        assert call_args[0][2] == mock_user  # current_user

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_cancel_appointment_success(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user):
        """Test successful appointment cancellation with email cancellation"""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.cancel_appointment_with_email.return_value = None
        mock_service_class.return_value = mock_service

        # Make request
        response = client.delete("/v1/appointments/appointment-123")

        # Verify response
        assert response.status_code == 204

        # Verify service was called
        mock_service.cancel_appointment_with_email.assert_called_once_with(
            "appointment-123", mock_user
        )

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_create_appointment_service_error(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user):
        """Test appointment creation with service error"""
        from app.services.exceptions import ServiceException
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.create_appointment.side_effect = ServiceException("CONFLICT_ERROR", "Time slot conflict")
        mock_service_class.return_value = mock_service

        # Test data
        appointment_data = {
            "care_provider_id": "provider-123",
            "start_time": "2024-01-15T14:00:00Z",
            "end_time": "2024-01-15T15:00:00Z"
        }

        # Make request
        response = client.post("/v1/appointments/", json=appointment_data)

        # Verify error response
        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "Time slot conflict" in data["detail"]

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_reschedule_appointment_not_found(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user):
        """Test rescheduling non-existent appointment"""
        from app.services.exceptions import ServiceException
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.reschedule_appointment.side_effect = ServiceException("NOT_FOUND", "Appointment not found")
        mock_service_class.return_value = mock_service

        # Test data
        reschedule_data = {
            "start_time": "2024-01-15T16:00:00Z",
            "end_time": "2024-01-15T17:00:00Z"
        }

        # Make request
        response = client.put("/v1/appointments/nonexistent/reschedule", json=reschedule_data)

        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch('app.api.appointments.AppointmentService')
    @patch('app.api.appointments.get_current_user_from_auth')
    @patch('app.api.appointments.get_db')
    def test_cancel_appointment_permission_error(self, mock_get_db, mock_get_user, mock_service_class, client, mock_user):
        """Test cancelling appointment without permission"""
        from app.services.exceptions import ServiceException
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = Mock(spec=Session)
        
        mock_service = Mock()
        mock_service.cancel_appointment_with_email.side_effect = ServiceException(
            "PERMISSION_ERROR", "Not authorized to cancel this appointment"
        )
        mock_service_class.return_value = mock_service

        # Make request
        response = client.delete("/v1/appointments/appointment-123")

        # Verify error response
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "Not authorized" in data["detail"]


@pytest.fixture
def client():
    """Create test client"""
    from main import app
    return TestClient(app)


class TestWebhookEndpoints:
    """Test webhook endpoints"""

    @patch('app.api.webhooks.mailgun_service')
    @patch('app.api.webhooks.AppointmentService')
    def test_mailgun_webhook_delivered_event(self, mock_service_class, mock_mailgun, client):
        """Test Mailgun webhook for delivered event"""
        # Setup mocks
        mock_mailgun.verify_webhook_signature.return_value = True
        
        mock_service = Mock()
        mock_service.update_email_delivery_status.return_value = None
        mock_service_class.return_value = mock_service

        # Test webhook data
        webhook_data = {
            "token": "test-token",
            "timestamp": "1234567890",
            "signature": "test-signature",
            "event": "delivered",
            "Message-Id": "message-123",
            "recipient": "test@example.com",
            "appointment_id": "appointment-123"
        }

        # Make request
        response = client.post("/v1/webhooks/mailgun", data=webhook_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event"] == "delivered"
        assert data["appointment_id"] == "appointment-123"

        # Verify service was called
        mock_service.update_email_delivery_status.assert_called_once_with(
            "appointment-123", "delivered"
        )

    @patch('app.api.webhooks.mailgun_service')
    def test_mailgun_webhook_invalid_signature(self, mock_mailgun, client):
        """Test Mailgun webhook with invalid signature"""
        # Setup mocks
        mock_mailgun.verify_webhook_signature.return_value = False

        # Test webhook data
        webhook_data = {
            "token": "test-token",
            "timestamp": "1234567890",
            "signature": "invalid-signature",
            "event": "delivered"
        }

        # Make request
        response = client.post("/v1/webhooks/mailgun", data=webhook_data)

        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "Invalid webhook signature" in data["detail"]

    @patch('app.api.webhooks.mailgun_service')
    @patch('app.api.webhooks.AppointmentService')
    def test_mailgun_webhook_opened_event(self, mock_service_class, mock_mailgun, client):
        """Test Mailgun webhook for opened event"""
        # Setup mocks
        mock_mailgun.verify_webhook_signature.return_value = True
        
        mock_service = Mock()
        mock_service.update_email_delivery_status.return_value = None
        mock_service_class.return_value = mock_service

        # Test webhook data
        webhook_data = {
            "token": "test-token",
            "timestamp": "1234567890",
            "signature": "test-signature",
            "event": "opened",
            "Message-Id": "message-123",
            "recipient": "test@example.com",
            "v:appointment_id": "appointment-123"  # Custom variable format
        }

        # Make request
        response = client.post("/v1/webhooks/mailgun", data=webhook_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event"] == "opened"

        # Verify service was called
        mock_service.update_email_delivery_status.assert_called_once_with(
            "appointment-123", "opened"
        )

    @patch('app.api.webhooks.mailgun_service')
    def test_mailgun_webhook_no_appointment_id(self, mock_mailgun, client):
        """Test Mailgun webhook without appointment ID"""
        # Setup mocks
        mock_mailgun.verify_webhook_signature.return_value = True

        # Test webhook data without appointment ID
        webhook_data = {
            "token": "test-token",
            "timestamp": "1234567890",
            "signature": "test-signature",
            "event": "delivered",
            "Message-Id": "message-123",
            "recipient": "test@example.com"
        }

        # Make request
        response = client.post("/v1/webhooks/mailgun", data=webhook_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "no appointment ID"

    def test_mailgun_webhook_test_endpoint(self, client):
        """Test Mailgun webhook test endpoint"""
        response = client.get("/v1/webhooks/mailgun/test")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "accessible" in data["message"]
        assert "configured" in data
