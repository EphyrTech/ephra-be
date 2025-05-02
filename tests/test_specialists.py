import pytest


def test_get_specialists(authorized_client, test_specialist):
    # Test getting all specialists
    response = authorized_client.get("/specialists")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_specialist.id
    assert data[0]["name"] == test_specialist.name
    assert data[0]["email"] == test_specialist.email
    assert data[0]["specialist_type"] == test_specialist.specialist_type
    assert data[0]["bio"] == test_specialist.bio
    assert data[0]["hourly_rate"] == test_specialist.hourly_rate


def test_get_specialists_unauthorized(client):
    # Test getting specialists without authentication
    response = client.get("/specialists")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_get_specialist(authorized_client, test_specialist):
    # Test getting a specific specialist
    response = authorized_client.get(f"/specialists/{test_specialist.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_specialist.id
    assert data["name"] == test_specialist.name
    assert data["email"] == test_specialist.email
    assert data["specialist_type"] == test_specialist.specialist_type
    assert data["bio"] == test_specialist.bio
    assert data["hourly_rate"] == test_specialist.hourly_rate


def test_get_specialist_not_found(authorized_client):
    # Test getting a non-existent specialist
    response = authorized_client.get("/specialists/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_specialist_unauthorized(client, test_specialist):
    # Test getting a specialist without authentication
    response = client.get(f"/specialists/{test_specialist.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_get_specialist_availability(authorized_client, test_specialist, test_availability):
    # Test getting a specialist's availability
    response = authorized_client.get(f"/specialists/{test_specialist.id}/availability")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_availability.id
    assert data[0]["specialist_id"] == test_specialist.id
    # Check that start_time and end_time are included in the response
    assert "start_time" in data[0]
    assert "end_time" in data[0]


def test_get_specialist_availability_not_found(authorized_client):
    # Test getting availability for a non-existent specialist
    response = authorized_client.get("/specialists/nonexistent-id/availability")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_specialist_availability_unauthorized(client, test_specialist):
    # Test getting a specialist's availability without authentication
    response = client.get(f"/specialists/{test_specialist.id}/availability")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()
