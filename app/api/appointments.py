from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_from_auth
from app.api.rbac_deps import (
    require_cancel_appointments,
    require_care_provider_or_admin,
    require_create_appointments,
    require_update_appointments,
    require_view_assigned_users,
)
from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.rbac import Scopes, has_scope
from app.db.database import get_db
from app.db.models import User, UserAssignment, UserRole
from app.schemas.appointment import Appointment as AppointmentSchema
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentUpdate,
)
from app.services.appointment_service import AppointmentService
from app.services.exceptions import ServiceException

router = APIRouter()


@router.get("/assigned-users", response_model=List[dict])
def get_assigned_users(
    auth: AuthInfo = Depends(require_view_assigned_users),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get users assigned to the current care provider.
    Returns users that are actually assigned to the care provider through the assignment system.
    Requires 'view:assigned-users' scope.
    """
    # Check if user has admin scope for broader access
    if has_scope(auth, Scopes.MANAGE_ALL_USERS):
        # Admins can see all active users
        users = (
            db.query(User)
            .filter(User.role == UserRole.USER, User.is_active == True)
            .all()
        )
    else:
        # Care providers see only users assigned to them
        assignments = (
            db.query(UserAssignment)
            .filter(
                UserAssignment.care_provider_id == current_user.id,
                UserAssignment.is_active == True,
            )
            .all()
        )

        user_ids = [assignment.user_id for assignment in assignments]
        users = (
            db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
            if user_ids
            else []
        )

    return [
        {
            "id": user.id,
            "name": user.name
            or f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "email": user.email,
            "role": user.role.value if user.role else "USER",
        }
        for user in users
    ]


@router.get("/")
def get_appointments(
    skip: int = 0,
    limit: int = 100,
    auth: AuthInfo = Depends(verify_access_token),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve appointments based on user permissions:
    - Users with 'view:all-appointments' scope: all appointments
    - Users with 'join:appointments' scope: their own appointments
    - Care providers: appointments where they are the care provider
    """
    try:
        appointment_service = AppointmentService(db)
        appointments = appointment_service.get_appointments_for_user(
            current_user, skip, limit
        )
        return appointments
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/", response_model=AppointmentSchema, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_in: AppointmentCreate,
    auth: AuthInfo = Depends(require_create_appointments),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new appointment using the service layer.
    Requires 'create:appointments' scope.
    - Users with scope: Create appointments for themselves
    - Care providers with scope: Create appointments for their assigned users
    - Admins with scope: Create appointments for any user
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.create_appointment(
            appointment_in, current_user
        )
        return appointment
    except ServiceException as e:
        # Map service exceptions to appropriate HTTP status codes
        status_map = {
            "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "PERMISSION_ERROR": status.HTTP_403_FORBIDDEN,
            "CONFLICT_ERROR": status.HTTP_409_CONFLICT,
            "BUSINESS_RULE_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
        error_code = e.error_code or "UNKNOWN_ERROR"
        status_code = status_map.get(
            error_code, status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=e.message)


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific appointment by id with full user details.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.get_appointment_with_details(
            appointment_id, current_user
        )
        return appointment
    except ServiceException as e:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in e.message.lower()
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=e.message)


@router.put("/{appointment_id}/reschedule", response_model=AppointmentSchema)
def reschedule_appointment(
    appointment_id: str,
    reschedule_data: AppointmentReschedule,
    auth: AuthInfo = Depends(require_update_appointments),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Reschedule an appointment and update email reminder.
    Requires 'update:appointments' scope.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.reschedule_appointment(
            appointment_id, reschedule_data, current_user
        )
        return appointment
    except ServiceException as e:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in e.message.lower()
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=e.message)


@router.put("/{appointment_id}", response_model=AppointmentSchema)
def update_appointment(
    appointment_id: str,
    appointment_in: AppointmentUpdate,
    auth: AuthInfo = Depends(require_update_appointments),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update an appointment.
    Requires 'update:appointments' scope.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.update_appointment(
            appointment_id, appointment_in, current_user
        )
        return appointment
    except ServiceException as e:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in e.message.lower()
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=e.message)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_appointment(
    appointment_id: str,
    auth: AuthInfo = Depends(require_cancel_appointments),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> None:
    """
    Cancel an appointment and its reminder email.
    Requires 'cancel:appointments' scope.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment_service.cancel_appointment_with_email(appointment_id, current_user)
    except ServiceException as e:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in e.message.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=e.message)
