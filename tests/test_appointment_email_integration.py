"""Integration tests for appointment service with email functionality"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Appointment, AppointmentStatus, User, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule
from app.services.appointment_service import AppointmentService


class TestAppointmentServiceEmailIntegration:
    """Test appointment service email integration"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_user(self):
        """Mock user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "patient@example.com"
        user.full_name = "John Doe"
        user.role = UserRole.USER
        return user

    @pytest.fixture
    def mock_care_provider(self):
        """Mock care provider"""
        provider = Mock(spec=User)
        provider.id = "provider-123"
        provider.email = "provider@example.com"
        provider.full_name = "Dr. Smith"
        provider.role = UserRole.CARE_PROVIDER
        return provider

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
        appointment.email_message_id = None
        appointment.email_scheduled = False
        appointment.email_delivered = False
        appointment.email_opened = False
        return appointment

    @patch('app.services.appointment_service.mailgun_service')
    def test_create_appointment_schedules_email(self, mock_mailgun_service, mock_db, mock_user, mock_care_provider):
        """Test that creating an appointment schedules an email reminder"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_care_provider,  # Care provider lookup
            mock_user,           # User lookup for email
            mock_care_provider   # Care provider lookup for email
        ]
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None  # No conflicts

        mock_mailgun_service.schedule_appointment_reminder.return_value = "message-123"

        # Create appointment data
        appointment_data = AppointmentCreate(
            care_provider_id="provider-123",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
            user_id="user-123",
            reminder_minutes=15
        )

        # Create service and call method
        service = AppointmentService(mock_db)

        with patch.object(service, '_get_active_care_provider', return_value=mock_care_provider), \
             patch.object(service, '_check_appointment_conflicts'), \
             patch.object(service, '_generate_meeting_link', return_value="https://meet.example.com/test"):

            result = service.create_appointment(appointment_data, mock_user)

        # Verify email was scheduled
        mock_mailgun_service.schedule_appointment_reminder.assert_called_once()
        call_args = mock_mailgun_service.schedule_appointment_reminder.call_args
        assert call_args[1]['to_email'] == str(mock_user.email)
        assert 'appointment_data' in call_args[1]

    @patch('app.services.appointment_service.mailgun_service')
    def test_create_appointment_email_failure_continues(self, mock_mailgun_service, mock_db, mock_user, mock_care_provider):
        """Test that appointment creation continues even if email scheduling fails"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_care_provider,  # Care provider lookup
            mock_user,           # User lookup for email
            mock_care_provider   # Care provider lookup for email
        ]
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None  # No conflicts

        # Email service fails
        mock_mailgun_service.schedule_appointment_reminder.return_value = None

        appointment_data = AppointmentCreate(
            care_provider_id="provider-123",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
            user_id="user-123"
        )

        service = AppointmentService(mock_db)

        with patch.object(service, '_get_active_care_provider', return_value=mock_care_provider), \
             patch.object(service, '_check_appointment_conflicts'), \
             patch.object(service, '_generate_meeting_link', return_value="https://meet.example.com/test"):

            # Should not raise exception even if email fails
            service.create_appointment(appointment_data, mock_user)

        # Verify email was attempted
        mock_mailgun_service.schedule_appointment_reminder.assert_called_once()

    @patch('app.services.appointment_service.mailgun_service')
    def test_reschedule_appointment_cancels_and_reschedules_email(
        self, mock_mailgun, mock_db, mock_user, mock_appointment
    ):
        """Test that rescheduling cancels old email and schedules new one"""
        # Setup mocks
        mock_appointment.email_message_id = "old-message-123"
        mock_appointment.email_scheduled = True

        mock_mailgun.cancel_scheduled_email.return_value = True
        mock_mailgun.schedule_appointment_reminder.return_value = "new-message-123"

        reschedule_data = AppointmentReschedule(
            start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            end_time=datetime.now(timezone.utc) + timedelta(hours=3),
            reminder_minutes=30
        )

        service = AppointmentService(mock_db)

        with patch.object(service, '_get_appointment_with_permission', return_value=mock_appointment), \
             patch.object(service, '_check_appointment_conflicts'), \
             patch('app.services.appointment_service.datetime') as mock_datetime:

            mock_datetime.now.return_value = datetime.now(timezone.utc)
            mock_datetime.timezone = timezone

            service.reschedule_appointment("appointment-123", reschedule_data, mock_user)

        # Verify old email was cancelled
        mock_mailgun.cancel_scheduled_email.assert_called_once_with("old-message-123")

        # Verify new email was scheduled
        mock_mailgun.schedule_appointment_reminder.assert_called_once()

    @patch('app.services.appointment_service.mailgun_service')
    def test_cancel_appointment_cancels_email(self, mock_mailgun, mock_db, mock_user, mock_appointment):
        """Test that cancelling appointment cancels the email"""
        # Setup mocks
        mock_appointment.email_message_id = "message-123"
        mock_appointment.email_scheduled = True
        mock_appointment.status = AppointmentStatus.PENDING
        
        mock_mailgun.cancel_scheduled_email.return_value = True

        service = AppointmentService(mock_db)
        
        with patch.object(service, '_get_appointment_with_permission', return_value=mock_appointment), \
             patch('app.services.appointment_service.datetime') as mock_datetime:
            
            mock_datetime.now.return_value = datetime.now(timezone.utc)
            mock_datetime.timezone = timezone
            
            service.cancel_appointment_with_email("appointment-123", mock_user)

        # Verify email was cancelled
        mock_mailgun.cancel_scheduled_email.assert_called_once_with("message-123")
        
        # Verify appointment status was updated
        assert mock_appointment.status == AppointmentStatus.CANCELLED

    def test_update_email_delivery_status_delivered(self, mock_db):
        """Test updating email delivery status to delivered"""
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.email_delivered = False
        mock_appointment.email_opened = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_appointment

        service = AppointmentService(mock_db)
        service.update_email_delivery_status("appointment-123", "delivered")

        assert mock_appointment.email_delivered is True
        mock_db.commit.assert_called_once()

    def test_update_email_delivery_status_opened(self, mock_db):
        """Test updating email delivery status to opened"""
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.email_delivered = False
        mock_appointment.email_opened = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_appointment

        service = AppointmentService(mock_db)
        service.update_email_delivery_status("appointment-123", "opened")

        assert mock_appointment.email_opened is True
        mock_db.commit.assert_called_once()

    def test_update_email_delivery_status_appointment_not_found(self, mock_db):
        """Test updating email delivery status when appointment not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = AppointmentService(mock_db)
        
        # Should not raise exception
        service.update_email_delivery_status("nonexistent-id", "delivered")
        
        # Should not call commit
        mock_db.commit.assert_not_called()

    @patch('app.services.appointment_service.mailgun_service')
    def test_schedule_reminder_email_past_delivery_time(self, mock_mailgun_service, mock_db, mock_appointment):
        """Test that emails are not scheduled for past delivery times"""
        # Set appointment time in the past
        mock_appointment.start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_appointment.reminder_minutes = 15

        mock_user = Mock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"

        mock_care_provider = Mock(spec=User)
        mock_care_provider.full_name = "Dr. Test"

        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_user, mock_care_provider]

        service = AppointmentService(mock_db)
        service._schedule_reminder_email(mock_appointment)

        # Email service should not be called for past delivery times
        mock_mailgun_service.schedule_appointment_reminder.assert_not_called()

    @patch('app.services.appointment_service.mailgun_service')
    def test_schedule_reminder_email_no_user_email(self, mock_mailgun_service, mock_db, mock_appointment):
        """Test that emails are not scheduled when user has no email"""
        mock_user = Mock(spec=User)
        mock_user.email = None  # No email
        mock_user.full_name = "Test User"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        service = AppointmentService(mock_db)
        service._schedule_reminder_email(mock_appointment)

        # Email service should not be called when user has no email
        mock_mailgun_service.schedule_appointment_reminder.assert_not_called()
