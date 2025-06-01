import pytest
from datetime import datetime, timedelta


def test_get_appointments(authorized_client, test_appointment):
    # Test getting all appointments
    response = authorized_client.get("/appointments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_appointment.id
    assert data[0]["user_id"] == test_appointment.user_id
    assert data[0]["specialist_id"] == test_appointment.specialist_id
    assert data[0]["status"] == test_appointment.status


def test_get_appointments_unauthorized(client):
    # Test getting appointments without authentication
    response = client.get("/appointments")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_create_appointment(authorized_client, test_user, test_specialist, test_availability):
    # Test creating a new appointment
    # Use the test_availability time range
    start_time = test_availability.start_time
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/appointments",
        json={
            "specialist_id": test_specialist.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["specialist_id"] == test_specialist.id
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert "meeting_link" in data


def test_create_appointment_invalid_time(authorized_client, test_specialist):
    # Test creating an appointment with invalid time (outside availability)
    start_time = datetime.utcnow() + timedelta(days=10)  # Far in the future, no availability
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/appointments",
        json={
            "specialist_id": test_specialist.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )
    assert response.status_code == 400
    assert "not available" in response.json()["detail"].lower()


def test_create_appointment_nonexistent_specialist(authorized_client):
    # Test creating an appointment with a non-existent specialist
    start_time = datetime.utcnow() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/appointments",
        json={
            "specialist_id": "nonexistent-id",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_appointment_unauthorized(client, test_specialist):
    # Test creating an appointment without authentication
    start_time = datetime.utcnow() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    response = client.post(
        "/appointments",
        json={
            "specialist_id": test_specialist.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_get_appointment(authorized_client, test_appointment):
    # Test getting a specific appointment
    response = authorized_client.get(f"/appointments/{test_appointment.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_appointment.id
    assert data["user_id"] == test_appointment.user_id
    assert data["specialist_id"] == test_appointment.specialist_id
    assert data["status"] == test_appointment.status


def test_get_appointment_not_found(authorized_client):
    # Test getting a non-existent appointment
    response = authorized_client.get("/appointments/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_appointment_unauthorized(client, test_appointment):
    # Test getting an appointment without authentication
    response = client.get(f"/appointments/{test_appointment.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_update_appointment(authorized_client, test_appointment, db):
    # Test updating an appointment status
    response = authorized_client.put(
        f"/appointments/{test_appointment.id}",
        json={
            "status": "cancelled"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_appointment.id
    assert data["status"] == "cancelled"

    # Verify the database was updated
    db.refresh(test_appointment)
    assert test_appointment.status == "cancelled"


def test_update_appointment_not_found(authorized_client):
    # Test updating a non-existent appointment
    response = authorized_client.put(
        "/appointments/nonexistent-id",
        json={
            "status": "cancelled"
        }
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_appointment_unauthorized(client, test_appointment):
    # Test updating an appointment without authentication
    response = client.put(
        f"/appointments/{test_appointment.id}",
        json={
            "status": "cancelled"
        }
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_delete_appointment(authorized_client, test_appointment, db):
    # Test cancelling an appointment (delete endpoint)
    response = authorized_client.delete(f"/appointments/{test_appointment.id}")
    assert response.status_code == 204

    # Verify the appointment status was changed to cancelled
    db.refresh(test_appointment)
    assert test_appointment.status == "cancelled"


def test_delete_appointment_not_found(authorized_client):
    # Test cancelling a non-existent appointment
    response = authorized_client.delete("/appointments/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_care_provider_can_create_appointment_anytime(care_provider_client, test_user):
    """
    Test that care providers can create appointments at any time for their patients,
    regardless of their availability slots.
    """
    # Create an appointment at a time when the care provider has no availability
    # This should succeed because care providers manage their own schedules
    start_time = datetime.utcnow() + timedelta(days=5, hours=8)  # Random future time
    end_time = start_time + timedelta(hours=1)

    response = care_provider_client.post(
        "/appointments/",
        json={
            "user_id": test_user.id,  # Care provider creating appointment for user
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert "meeting_link" in data


def test_regular_user_restricted_by_availability(authorized_client, care_provider_user):
    """
    Test that regular users are still restricted by care provider availability
    when booking appointments.
    """
    # Try to create an appointment at a time when the care provider has no availability
    start_time = datetime.utcnow() + timedelta(days=10)  # Far in the future, no availability
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/appointments/",
        json={
            "care_provider_id": care_provider_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    )

    # This should fail because regular users must respect care provider availability
    assert response.status_code == 409  # Conflict error
    assert "not available" in response.json()["detail"].lower()


def test_delete_appointment_unauthorized(client, test_appointment):
    # Test cancelling an appointment without authentication
    response = client.delete(f"/appointments/{test_appointment.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()
