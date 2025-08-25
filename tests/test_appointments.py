from datetime import datetime, timedelta, timezone

import pytest


def test_get_appointments(authorized_client, test_appointment):
    # Test getting all appointments
    response = authorized_client.get("/v1/appointments/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_appointment.id
    assert data[0]["user_id"] == test_appointment.user_id
    assert data[0]["care_provider_id"] == test_appointment.care_provider_id
    assert data[0]["status"] == test_appointment.status


def test_get_appointments_unauthorized(client):
    # Test getting appointments without authentication
    response = client.get("/v1/appointments/")
    assert response.status_code in [401, 403]
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert (
        "not authenticated" in error_message.lower()
        or "forbidden" in error_message.lower()
    )


def test_create_appointment(
    authorized_client, test_user, test_specialist, test_availability
):
    # Test creating a new appointment
    # Use the test_availability time range
    start_time = test_availability.start_time
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/v1/appointments/",
        json={
            "care_provider_id": test_specialist.user_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["care_provider_id"] == test_specialist.user_id
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert "meeting_link" in data


def test_create_appointment_invalid_time(authorized_client, test_specialist):
    # Test creating an appointment with invalid time (outside availability)
    start_time = datetime.now(timezone.utc) + timedelta(
        days=10
    )  # Far in the future, no availability
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/v1/appointments/",
        json={
            "care_provider_id": test_specialist.user_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code in [400, 422]
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert (
        "not available" in error_message.lower()
        or "validation" in error_message.lower()
    )


def test_create_appointment_nonexistent_specialist(authorized_client):
    # Test creating an appointment with a non-existent specialist
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/v1/appointments",
        json={
            "care_provider_id": "nonexistent-id",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code in [404, 422]
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert "not found" in error_message.lower() or "validation" in error_message.lower()


def test_create_appointment_unauthorized(client, test_specialist):
    # Test creating an appointment without authentication
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)

    response = client.post(
        "/v1/appointments",
        json={
            "care_provider_id": test_specialist.user_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code in [401, 403]
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert (
        "not authenticated" in error_message.lower()
        or "forbidden" in error_message.lower()
    )


def test_get_appointment(authorized_client, test_appointment):
    # Test getting a specific appointment
    response = authorized_client.get(f"/v1/appointments/{test_appointment.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_appointment.id
    assert data["user_id"] == test_appointment.user_id
    assert data["care_provider_id"] == test_appointment.care_provider_id
    assert data["status"] == test_appointment.status


def test_get_appointment_not_found(authorized_client):
    # Test getting a non-existent appointment
    response = authorized_client.get("/v1/appointments/nonexistent-id")
    assert response.status_code == 404
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert "not found" in error_message.lower()


def test_get_appointment_unauthorized(client, test_appointment):
    # Test getting an appointment without authentication
    response = client.get(f"/v1/appointments/{test_appointment.id}")
    assert response.status_code in [401, 403]
    response_data = response.json()
    error_message = response_data.get(
        "detail", response_data.get("error", {}).get("message", "")
    )
    assert (
        "not authenticated" in error_message.lower()
        or "forbidden" in error_message.lower()
    )


def test_update_appointment(authorized_client, test_appointment, db):
    # Test updating an appointment status
    response = authorized_client.put(
        f"/v1/appointments/{test_appointment.id}", json={"status": "cancelled"}
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
        "/v1/appointments/nonexistent-id", json={"status": "cancelled"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_appointment_unauthorized(client, test_appointment):
    # Test updating an appointment without authentication
    response = client.put(
        f"/v1/appointments/{test_appointment.id}", json={"status": "cancelled"}
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_delete_appointment(authorized_client, test_appointment, db):
    # Test cancelling an appointment (delete endpoint)
    response = authorized_client.delete(f"/v1/appointments/{test_appointment.id}")
    assert response.status_code == 204

    # Verify the appointment status was changed to cancelled
    db.refresh(test_appointment)
    assert test_appointment.status == "cancelled"


def test_delete_appointment_not_found(authorized_client):
    # Test cancelling a non-existent appointment
    response = authorized_client.delete("/v1/appointments/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_care_provider_can_create_appointment_anytime(care_provider_client, test_user):
    """
    Test that care providers can create appointments at any time for their patients,
    regardless of their availability slots.
    """
    # Create an appointment at a time when the care provider has no availability
    # This should succeed because care providers manage their own schedules
    start_time = datetime.now(timezone.utc) + timedelta(
        days=5, hours=8
    )  # Random future time
    end_time = start_time + timedelta(hours=1)

    response = care_provider_client.post(
        "/v1/appointments/",
        json={
            "user_id": test_user.id,  # Care provider creating appointment for user
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert "meeting_link" in data


def test_care_provider_can_add_custom_meeting_link(care_provider_client, test_user):
    """
    Test that care providers can add custom meeting links when creating appointments.
    """
    start_time = datetime.now(timezone.utc) + timedelta(days=1, hours=10)
    end_time = start_time + timedelta(hours=1)
    custom_meeting_link = "https://zoom.us/j/123456789"

    response = care_provider_client.post(
        "/v1/appointments/",
        json={
            "user_id": test_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "meeting_link": custom_meeting_link,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert data["meeting_link"] == custom_meeting_link


def test_care_provider_can_add_notes_to_appointment(care_provider_client, test_user):
    """
    Test that care providers can add notes when creating appointments.
    """
    start_time = datetime.now(timezone.utc) + timedelta(days=1, hours=16)
    end_time = start_time + timedelta(hours=1)
    appointment_notes = "Initial consultation - discuss treatment plan"

    response = care_provider_client.post(
        "/v1/appointments/",
        json={
            "user_id": test_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "notes": appointment_notes,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert data["notes"] == appointment_notes


def test_care_provider_can_add_both_meeting_link_and_notes(
    care_provider_client, test_user
):
    """
    Test that care providers can add both meeting link and notes when creating appointments.
    """
    start_time = datetime.now(timezone.utc) + timedelta(days=2, hours=10)
    end_time = start_time + timedelta(hours=1)
    custom_meeting_link = "https://teams.microsoft.com/l/meetup-join/123"
    appointment_notes = "Follow-up session - review progress and adjust goals"

    response = care_provider_client.post(
        "/v1/appointments/",
        json={
            "user_id": test_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "meeting_link": custom_meeting_link,
            "notes": appointment_notes,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert data["meeting_link"] == custom_meeting_link
    assert data["notes"] == appointment_notes


def test_care_provider_auto_generates_meeting_link_when_not_provided(
    care_provider_client, test_user
):
    """
    Test that when no custom meeting link is provided, the system auto-generates one.
    """
    start_time = datetime.now(timezone.utc) + timedelta(days=1, hours=14)
    end_time = start_time + timedelta(hours=1)

    response = care_provider_client.post(
        "/v1/appointments/",
        json={
            "user_id": test_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            # No meeting_link provided
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["status"] == "pending"
    assert "meeting_link" in data
    assert data["meeting_link"] is not None
    assert data["meeting_link"].startswith("https://meet.example.com/")


def test_regular_user_restricted_by_availability(authorized_client, care_provider_user):
    """
    Test that regular users are still restricted by care provider availability
    when booking appointments.
    """
    # Try to create an appointment at a time when the care provider has no availability
    start_time = datetime.now(timezone.utc) + timedelta(
        days=10
    )  # Far in the future, no availability
    end_time = start_time + timedelta(hours=1)

    response = authorized_client.post(
        "/v1/appointments/",
        json={
            "care_provider_id": care_provider_user.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )

    # This should fail because regular users must respect care provider availability
    assert response.status_code == 409  # Conflict error
    assert "not available" in response.json()["detail"].lower()


def test_delete_appointment_unauthorized(client, test_appointment):
    # Test cancelling an appointment without authentication
    response = client.delete(f"/v1/appointments/{test_appointment.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()
