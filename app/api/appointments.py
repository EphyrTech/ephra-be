from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, UserRole
from app.schemas.appointment import (
    Appointment as AppointmentSchema,
    AppointmentCreate,
    AppointmentUpdate,
)
from app.api.deps import get_current_user
from app.api.role_deps import require_care_or_admin
from app.services.appointment_service import AppointmentService
from app.services.exceptions import ServiceException

router = APIRouter()


@router.get("/assigned-users", response_model=List[dict])
def get_assigned_users(
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get users assigned to the current care provider.
    For now, returns all active users since we don't have explicit assignment yet.
    Care providers can create appointments for any active user.
    """
    if current_user.role == UserRole.CARE_PROVIDER:
        # For care providers, return all active users they can create appointments for
        users = db.query(User).filter(
            User.role == UserRole.USER,
            User.is_active == True
        ).all()
    elif current_user.role == UserRole.ADMIN:
        # Admins can see all users
        users = db.query(User).filter(User.is_active == True).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return [
        {
            "id": user.id,
            "name": user.name or f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "email": user.email,
            "role": user.role.value if user.role else "USER"
        }
        for user in users
    ]


@router.get("/")
def get_appointments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve appointments based on user role:
    - Regular users: their own appointments
    - Care providers: appointments where they are the care provider
    - Admins: all appointments
    """
    try:
        appointment_service = AppointmentService(db)
        appointments = appointment_service.get_appointments_for_user(current_user, skip, limit)
        return appointments
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/", response_model=AppointmentSchema, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_in: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new appointment using the service layer.
    - Regular users: Create appointments for themselves
    - Care providers: Create appointments for their assigned users
    - Admins: Create appointments for any user
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.create_appointment(appointment_in, current_user)
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
        status_code = status_map.get(e.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        raise HTTPException(status_code=status_code, detail=e.message)


@router.get("/{appointment_id}", response_model=AppointmentSchema)
def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific appointment by id.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service._get_appointment_with_permission(appointment_id, current_user)
        return appointment
    except ServiceException as e:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in e.message.lower() else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=e.message)


@router.put("/{appointment_id}", response_model=AppointmentSchema)
def update_appointment(
    appointment_id: str,
    appointment_in: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update an appointment.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment = appointment_service.update_appointment(appointment_id, appointment_in, current_user)
        return appointment
    except ServiceException as e:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in e.message.lower() else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=e.message)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Cancel an appointment.
    """
    try:
        appointment_service = AppointmentService(db)
        appointment_service.cancel_appointment(appointment_id, current_user)
    except ServiceException as e:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in e.message.lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=status_code, detail=e.message)
