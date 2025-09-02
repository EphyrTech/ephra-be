"""Appointment service for business logic"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import uuid
import pendulum
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Availability,
    CareProviderProfile,
    User,
    UserRole,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentUpdate,
)
from app.services.email_service import AppointmentEmailData, mailgun_service
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class AppointmentService:
    """Service for appointment-related business logic"""

    def __init__(self, db: Session):
        self.db = db

    def create_appointment(
        self, appointment_data: AppointmentCreate, current_user: User
    ) -> Appointment:
        """Create a new appointment with proper business logic"""

        # Determine user and care provider based on current user role
        if current_user.role is UserRole.USER:
            user_id = current_user.id
            care_provider_id = appointment_data.care_provider_id

            # Validate care provider exists and is active
            care_provider = self._get_active_care_provider(care_provider_id)

        elif current_user.role is UserRole.CARE_PROVIDER:
            # Care provider creating appointment for a user
            if not hasattr(appointment_data, "user_id") or not appointment_data.user_id:
                raise ValidationError(
                    "user_id is required when care provider creates appointment"
                )

            user_id = appointment_data.user_id
            care_provider_id = current_user.id

            # Validate user exists and is active
            user = self._get_active_user(user_id)
            care_provider = current_user

        elif current_user.role is UserRole.ADMIN:
            # Admin can create appointments for any user with any care provider
            user_id = appointment_data.user_id or current_user.id
            care_provider_id = appointment_data.care_provider_id

            user = self._get_active_user(user_id)
            care_provider = self._get_active_care_provider(care_provider_id)

        else:
            raise PermissionError("Insufficient permissions to create appointments")

        # Validate appointment time
        self._validate_appointment_time(
            appointment_data.start_time, appointment_data.end_time
        )

        # Check care provider availability only for regular users booking appointments
        # Care providers can create appointments at any time for their patients (they manage their own schedule)
        if current_user.role == UserRole.USER:
            self._check_care_provider_availability(
                care_provider_id, appointment_data.start_time, appointment_data.end_time
            )

        # Check for conflicts (always check to prevent double-booking)
        self._check_appointment_conflicts(
            care_provider_id, appointment_data.start_time, appointment_data.end_time
        )

        # Create appointment
        appointment = Appointment(
            user_id=user_id,
            care_provider_id=care_provider_id,
            start_time=appointment_data.start_time,
            end_time=appointment_data.end_time,
            status=AppointmentStatus.PENDING,
            meeting_link=appointment_data.meeting_link or self._generate_meeting_link(),
            notes=appointment_data.notes,
            reminder_minutes=appointment_data.reminder_minutes or 15,
        )

        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        # Schedule reminder email
        self._schedule_reminder_email(appointment)

        return appointment

    def get_appointments_for_user(
        self, user: User, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        """Get appointments based on user role with user details"""
        from sqlalchemy.orm import aliased

        # Create aliases for user tables to avoid conflicts
        patient_user = aliased(User)
        provider_user = aliased(User)

        query = (
            self.db.query(
                Appointment,
                patient_user.name.label("user_name"),
                patient_user.first_name.label("user_first_name"),
                patient_user.last_name.label("user_last_name"),
                patient_user.email.label("user_email"),
                patient_user.date_of_birth.label("user_date_of_birth"),
                patient_user.country.label("user_country"),
                provider_user.name.label("care_provider_name"),
                provider_user.first_name.label("care_provider_first_name"),
                provider_user.last_name.label("care_provider_last_name"),
                provider_user.email.label("care_provider_email"),
            )
            .join(patient_user, Appointment.user_id == patient_user.id)
            .join(provider_user, Appointment.care_provider_id == provider_user.id)
        )

        if user.role == UserRole.USER:
            # Regular users see only their own appointments
            query = query.filter(Appointment.user_id == user.id)
        elif user.role == UserRole.CARE_PROVIDER:
            # Care providers see appointments where they are the provider
            query = query.filter(Appointment.care_provider_id == user.id)
        # Admins see all appointments (no additional filter)

        results = query.order_by(Appointment.start_time).offset(skip).limit(limit).all()

        # Convert to list of dictionaries with appointment and user data
        appointments = []
        for result in results:
            appointment = result[0]  # The Appointment object

            # Build user name from available fields
            user_name = result.user_name
            if not user_name and (result.user_first_name or result.user_last_name):
                user_name = f"{result.user_first_name or ''} {result.user_last_name or ''}".strip()

            # Build care provider name from available fields
            care_provider_name = result.care_provider_name
            if not care_provider_name and (
                result.care_provider_first_name or result.care_provider_last_name
            ):
                care_provider_name = f"{result.care_provider_first_name or ''} {result.care_provider_last_name or ''}".strip()

            # Format date of birth as string if available
            user_date_of_birth = None
            if result.user_date_of_birth:
                user_date_of_birth = (
                    result.user_date_of_birth.isoformat()
                    if hasattr(result.user_date_of_birth, "isoformat")
                    else str(result.user_date_of_birth)
                )

            appointment_dict = {
                "id": appointment.id,
                "user_id": appointment.user_id,
                "care_provider_id": appointment.care_provider_id,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "status": appointment.status,
                "meeting_link": appointment.meeting_link,
                "notes": appointment.notes,
                "created_at": appointment.created_at,
                "updated_at": appointment.updated_at,
                "user_name": user_name,
                "user_email": result.user_email,
                "user_first_name": result.user_first_name,
                "user_last_name": result.user_last_name,
                "user_date_of_birth": user_date_of_birth,
                "user_country": result.user_country,
                "care_provider_name": care_provider_name,
                "care_provider_email": result.care_provider_email,
                "care_provider_first_name": result.care_provider_first_name,
                "care_provider_last_name": result.care_provider_last_name,
            }
            appointments.append(appointment_dict)

        return appointments

    def update_appointment(
        self, appointment_id: str, update_data: AppointmentUpdate, current_user: User
    ) -> Appointment:
        """Update an appointment with proper authorization"""
        appointment = self._get_appointment_with_permission(
            appointment_id, current_user
        )

        # Apply updates
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(appointment, field, value)

        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def cancel_appointment(self, appointment_id: str, current_user: User) -> None:
        """Cancel an appointment"""
        appointment = self._get_appointment_with_permission(
            appointment_id, current_user
        )

        if appointment.status == AppointmentStatus.CANCELLED:
            raise BusinessRuleError("Appointment is already cancelled")

        if appointment.status == AppointmentStatus.COMPLETED:
            raise BusinessRuleError("Cannot cancel a completed appointment")

        appointment.status = AppointmentStatus.CANCELLED
        self.db.commit()

    def _get_active_user(self, user_id: str) -> User:
        """Get an active user or raise NotFoundError"""
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.is_active == True)
            .first()
        )
        if not user:
            raise NotFoundError("User not found")
        return user

    def _get_active_care_provider(self, care_provider_id: str) -> User:
        """Get an active care provider or raise NotFoundError"""
        care_provider = (
            self.db.query(User)
            .filter(
                User.id == care_provider_id,
                User.role == UserRole.CARE_PROVIDER,
                User.is_active == True,
            )
            .first()
        )
        if not care_provider:
            raise NotFoundError("Care provider not found")
        return care_provider

    def _validate_appointment_time(
        self, start_time: datetime, end_time: datetime
    ) -> None:
        """Validate appointment time constraints"""
        if start_time >= end_time:
            raise ValidationError("Start time must be before end time")

        # Handle timezone comparison properly
        now = datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            # If start_time is naive, assume it's UTC
            start_time_aware = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time_aware = start_time

        if start_time_aware <= now:
            raise ValidationError("Appointment cannot be scheduled in the past")

        duration = end_time - start_time
        if duration < timedelta(minutes=15):
            raise ValidationError("Appointment must be at least 15 minutes long")

        if duration > timedelta(hours=4):
            raise ValidationError("Appointment cannot be longer than 4 hours")

    def _check_care_provider_availability(
        self, care_provider_id: str, start_time: datetime, end_time: datetime
    ) -> None:
        """
        Check if care provider is available during the requested time.

        This should only be called when regular users are booking appointments with care providers.
        Care providers creating appointments for their patients should bypass this check
        since they manage their own schedules.
        """
        # Get care provider profile
        profile = (
            self.db.query(CareProviderProfile)
            .filter(CareProviderProfile.user_id == care_provider_id)
            .first()
        )

        if not profile:
            raise NotFoundError("Care provider profile not found")

        if not profile.is_accepting_patients:
            raise BusinessRuleError(
                "Care provider is not currently accepting new patients"
            )

        # Check if any availability slots exist for this care provider
        has_availability_slots = (
            self.db.query(Availability)
            .filter(Availability.care_provider_id == profile.id)
            .first()
            is not None
        )

        # If no availability slots exist, allow any time (availability is optional)
        if not has_availability_slots:
            return

        # If availability slots exist, check if the requested time fits within them
        availability = (
            self.db.query(Availability)
            .filter(
                Availability.care_provider_id == profile.id,
                Availability.start_time <= start_time,
                Availability.end_time >= end_time,
                Availability.is_available == True,
            )
            .first()
        )

        if not availability:
            raise ConflictError(
                "Care provider is not available during the requested time"
            )

    def _check_appointment_conflicts(
        self, care_provider_id: str, start_time: datetime, end_time: datetime, exclude_appointment_id: Optional[str] = None
    ) -> None:
        """Check for overlapping appointments"""
        query = (
            self.db.query(Appointment)
            .filter(
                Appointment.care_provider_id == care_provider_id,
                Appointment.status.in_(
                    [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
                ),
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
            )
        )

        # Exclude the current appointment when rescheduling
        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)

        overlapping = query.first()

        if overlapping:
            raise ConflictError(
                "The requested time slot conflicts with an existing appointment"
            )

    def _get_appointment_with_permission(
        self, appointment_id: str, current_user: User
    ) -> Appointment:
        """Get appointment and check user has permission to access it"""
        appointment = (
            self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )

        if not appointment:
            raise NotFoundError("Appointment not found")

        # Check permissions
        if (
            current_user.role == UserRole.USER
            and appointment.user_id != current_user.id
        ):
            raise PermissionError("You can only access your own appointments")
        elif (
            current_user.role == UserRole.CARE_PROVIDER
            and appointment.care_provider_id != current_user.id
        ):
            raise PermissionError(
                "You can only access appointments where you are the care provider"
            )
        # Admins can access all appointments

        return appointment

    def get_appointment_with_details(
        self, appointment_id: str, current_user: User
    ) -> dict:
        """Get appointment with full user details and check permissions"""
        from sqlalchemy.orm import aliased

        # Create aliases for user tables to avoid conflicts
        patient_user = aliased(User)
        provider_user = aliased(User)

        # Query appointment with user details
        result = (
            self.db.query(
                Appointment,
                patient_user.name.label("user_name"),
                patient_user.first_name.label("user_first_name"),
                patient_user.last_name.label("user_last_name"),
                patient_user.email.label("user_email"),
                patient_user.date_of_birth.label("user_date_of_birth"),
                patient_user.country.label("user_country"),
                provider_user.name.label("care_provider_name"),
                provider_user.first_name.label("care_provider_first_name"),
                provider_user.last_name.label("care_provider_last_name"),
                provider_user.email.label("care_provider_email"),
            )
            .join(patient_user, Appointment.user_id == patient_user.id)
            .join(provider_user, Appointment.care_provider_id == provider_user.id)
            .filter(Appointment.id == appointment_id)
            .first()
        )

        if not result:
            raise NotFoundError("Appointment not found")

        appointment = result[0]  # The Appointment object

        # Check permissions
        if (
            current_user.role == UserRole.USER
            and appointment.user_id != current_user.id
        ):
            raise PermissionError("You can only access your own appointments")
        elif (
            current_user.role == UserRole.CARE_PROVIDER
            and appointment.care_provider_id != current_user.id
        ):
            raise PermissionError(
                "You can only access appointments where you are the care provider"
            )
        # Admins can access all appointments

        # Build user name from available fields
        user_name = result.user_name
        if not user_name and (result.user_first_name or result.user_last_name):
            user_name = (
                f"{result.user_first_name or ''} {result.user_last_name or ''}".strip()
            )

        # Build care provider name from available fields
        care_provider_name = result.care_provider_name
        if not care_provider_name and (
            result.care_provider_first_name or result.care_provider_last_name
        ):
            care_provider_name = f"{result.care_provider_first_name or ''} {result.care_provider_last_name or ''}".strip()

        # Format date of birth as string if available
        user_date_of_birth = None
        if result.user_date_of_birth:
            user_date_of_birth = (
                result.user_date_of_birth.isoformat()
                if hasattr(result.user_date_of_birth, "isoformat")
                else str(result.user_date_of_birth)
            )

        appointment_dict = {
            "id": appointment.id,
            "user_id": appointment.user_id,
            "care_provider_id": appointment.care_provider_id,
            "start_time": appointment.start_time,
            "end_time": appointment.end_time,
            "status": appointment.status,
            "meeting_link": appointment.meeting_link,
            "notes": appointment.notes,
            "created_at": appointment.created_at,
            "updated_at": appointment.updated_at,
            "user_name": user_name,
            "user_email": result.user_email,
            "user_first_name": result.user_first_name,
            "user_last_name": result.user_last_name,
            "user_date_of_birth": user_date_of_birth,
            "user_country": result.user_country,
            "care_provider_name": care_provider_name,
            "care_provider_email": result.care_provider_email,
            "care_provider_first_name": result.care_provider_first_name,
            "care_provider_last_name": result.care_provider_last_name,
        }

        return appointment_dict

    def _generate_meeting_link(self) -> str:
        """Generate a meeting link (placeholder implementation)"""
        
        return f"{settings.MEETING_LINK_BASE_URL}/{uuid.uuid4()}"

    def _schedule_reminder_email(self, appointment: Appointment) -> None:
        """Schedule a reminder email for the appointment"""
        try:
            if not mailgun_service.is_configured():
                logger.warning("Mailgun not configured. Skipping email scheduling.")
                return

            # Get user and care provider details
            user = self.db.query(User).filter(User.id == appointment.user_id).first()
            care_provider = self.db.query(User).filter(User.id == appointment.care_provider_id).first()

            if not user or not user.email:
                logger.warning(f"User {appointment.user_id} not found or has no email. Skipping email.")
                return

            if not care_provider:
                logger.warning(f"Care provider {appointment.care_provider_id} not found. Skipping email.")
                return

            # Calculate delivery time (reminder_minutes before appointment)
            delivery_time = pendulum.instance(appointment.start_time).subtract(minutes=appointment.reminder_minutes)

            # Don't schedule emails for past times
            if delivery_time <= datetime.now(timezone.utc):
                logger.warning(f"Delivery time {delivery_time} is in the past. Skipping email scheduling.")
                return

            # Prepare appointment data for email template
            email_data = AppointmentEmailData(
                user_name=str(user.full_name or user.email),
                specialist_name=str(care_provider.full_name or care_provider.email),
                specialist_type="Mental Health",  # You can get this from care provider profile
                appointment_datetime=appointment.start_time.strftime("%B %d, %Y"),
                appointment_format="Video Call",  # Default format
                meeting_link=str(appointment.meeting_link or ""),
                company_name="Ephyr Health",
                support_email=settings.EMAIL_FROM,
                appointment_id=str(appointment.id),
                reminder_minutes=int(appointment.reminder_minutes)
            )

            # Schedule the email via Mailgun
            message_id = mailgun_service.schedule_appointment_reminder(
                to_email=str(user.email),
                appointment_data=email_data,
            )

            if message_id:
                # Update appointment with email tracking info
                appointment.email_message_id = message_id
                appointment.email_scheduled = True
                self.db.commit()
                logger.info(f"Scheduled reminder email for appointment {appointment.id}, message ID: {message_id}")
            else:
                logger.error(f"Failed to schedule reminder email for appointment {appointment.id}")

        except Exception as e:
            logger.error(f"Error scheduling reminder email for appointment {appointment.id}: {str(e)}")

    def _cancel_reminder_email(self, appointment: Appointment) -> None:
        """Cancel a scheduled reminder email"""
        try:
            if not appointment.email_message_id or not appointment.email_scheduled:
                return

            if mailgun_service.cancel_scheduled_email(appointment.email_message_id):
                appointment.email_scheduled = False
                self.db.commit()
                logger.info(f"Cancelled reminder email for appointment {appointment.id}")
            else:
                logger.warning(f"Failed to cancel reminder email for appointment {appointment.id}")

        except Exception as e:
            logger.error(f"Error cancelling reminder email for appointment {appointment.id}: {str(e)}")

    def reschedule_appointment(
        self,
        appointment_id: str,
        reschedule_data: AppointmentReschedule,
        current_user: User
    ) -> Appointment:
        """Reschedule an appointment and update email reminder"""
        # Get the appointment
        appointment = self._get_appointment_with_permission(appointment_id, current_user)

        if appointment.status == AppointmentStatus.CANCELLED:
            raise BusinessRuleError("Cannot reschedule a cancelled appointment")

        if appointment.status == AppointmentStatus.COMPLETED:
            raise BusinessRuleError("Cannot reschedule a completed appointment")

        # Check for conflicts with new time
        self._check_appointment_conflicts(
            appointment.care_provider_id,
            reschedule_data.start_time,
            reschedule_data.end_time,
            exclude_appointment_id=appointment_id
        )

        # Cancel existing reminder email if scheduled
        self._cancel_reminder_email(appointment)

        # Update appointment times
        appointment.start_time = reschedule_data.start_time
        appointment.end_time = reschedule_data.end_time
        appointment.reminder_minutes = reschedule_data.reminder_minutes or appointment.reminder_minutes
        appointment.updated_at = datetime.now(timezone.utc)

        # Reset email tracking fields
        appointment.email_message_id = None
        appointment.email_scheduled = False
        appointment.email_delivered = False
        appointment.email_opened = False

        self.db.commit()
        self.db.refresh(appointment)

        # Schedule new reminder email
        self._schedule_reminder_email(appointment)

        return appointment

    def cancel_appointment_with_email(self, appointment_id: str, current_user: User) -> None:
        """Cancel an appointment and its reminder email"""
        appointment = self._get_appointment_with_permission(appointment_id, current_user)

        if appointment.status == AppointmentStatus.CANCELLED:
            raise BusinessRuleError("Appointment is already cancelled")

        if appointment.status == AppointmentStatus.COMPLETED:
            raise BusinessRuleError("Cannot cancel a completed appointment")

        # Cancel reminder email if scheduled
        self._cancel_reminder_email(appointment)

        # Update appointment status
        appointment.status = AppointmentStatus.CANCELLED
        appointment.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_email_delivery_status(self, appointment_id: str, event_type: str) -> None:
        """Update email delivery status based on webhook events"""
        try:
            appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                logger.warning(f"Appointment {appointment_id} not found for email status update")
                return

            if event_type == "delivered":
                appointment.email_delivered = True
            elif event_type == "opened":
                appointment.email_opened = True

            self.db.commit()
            logger.info(f"Updated email status for appointment {appointment_id}: {event_type}")

        except Exception as e:
            logger.error(f"Error updating email status for appointment {appointment_id}: {str(e)}")
