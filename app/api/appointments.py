from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Appointment, User, Specialist, Availability, AppointmentStatus
from app.schemas.appointment import (
    Appointment as AppointmentSchema,
    AppointmentCreate,
    AppointmentUpdate,
)
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/", response_model=List[AppointmentSchema])
def get_appointments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve appointments.
    """
    appointments = (
        db.query(Appointment)
        .filter(Appointment.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return appointments


@router.post("/", response_model=AppointmentSchema, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_in: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new appointment.
    """
    # Check if specialist exists
    specialist = (
        db.query(Specialist)
        .filter(Specialist.id == appointment_in.specialist_id)
        .first()
    )
    if not specialist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specialist not found",
        )

    # Check if the time slot is available
    availability = (
        db.query(Availability)
        .filter(
            Availability.specialist_id == appointment_in.specialist_id,
            Availability.start_time <= appointment_in.start_time,
            Availability.end_time >= appointment_in.end_time,
        )
        .first()
    )

    if not availability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected time slot is not available",
        )

    # Check for overlapping appointments
    overlapping_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.specialist_id == appointment_in.specialist_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < appointment_in.end_time,
            Appointment.end_time > appointment_in.start_time,
        )
        .first()
    )

    if overlapping_appointment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected time slot overlaps with an existing appointment",
        )

    # Create appointment
    appointment = Appointment(
        **appointment_in.model_dump(),
        user_id=current_user.id,
        status=AppointmentStatus.PENDING,
    )

    # In a real implementation, you would create a Google Meet link here
    appointment.meeting_link = f"https://meet.google.com/example-{appointment.id}"

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/{appointment_id}", response_model=AppointmentSchema)
def get_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific appointment by id.
    """
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id, Appointment.user_id == current_user.id
        )
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return appointment


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
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id, Appointment.user_id == current_user.id
        )
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    update_data = appointment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(appointment, field, value)

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Cancel an appointment.
    """
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id, Appointment.user_id == current_user.id
        )
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Instead of deleting, mark as cancelled
    appointment.status = AppointmentStatus.CANCELLED
    db.add(appointment)
    db.commit()
