import pytest
from app.core.security import verify_password


def test_register_user(client):
    # Test user registration
    response = client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "name": "New User",
            "password": "password123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["name"] == "New User"
    assert "id" in data


def test_register_existing_user(client, test_user):
    # Test registering with an existing email
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",  # Same as test_user
            "name": "Another User",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_login_success(client, test_user):
    # Test successful login
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    # Test login with wrong password
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "incorrect email or password" in response.json()["detail"].lower()


def test_login_nonexistent_user(client):
    # Test login with non-existent user
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 401
    assert "incorrect email or password" in response.json()["detail"].lower()


def test_google_auth(client):
    # Test Google authentication (mock implementation)
    response = client.post(
        "/auth/google",
        json={
            "token": "mock_google_token"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_reset_password(client, test_user):
    # Test password reset request
    response = client.post(
        "/auth/reset-password",
        json={
            "email": "test@example.com"
        }
    )
    assert response.status_code == 200
    assert "message" in response.json()
    assert "password reset email sent" in response.json()["message"].lower()


def test_reset_password_nonexistent_user(client):
    # Test password reset for non-existent user
    response = client.post(
        "/auth/reset-password",
        json={
            "email": "nonexistent@example.com"
        }
    )
    assert response.status_code == 200
    # Should still return success to prevent user enumeration
    assert "message" in response.json()
    assert "password reset email sent" in response.json()["message"].lower()
