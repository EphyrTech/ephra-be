import pytest
from app.core.security import verify_password


def test_get_current_user(authorized_client, test_user):
    # Test getting current user info
    response = authorized_client.get("/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["name"] == test_user.name


def test_get_current_user_unauthorized(client):
    # Test getting current user without authentication
    response = client.get("/users/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_update_user(authorized_client, test_user, db):
    # Test updating user info
    response = authorized_client.put(
        "/users/me",
        json={
            "name": "Updated Name",
            "email": "updated@example.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["email"] == "updated@example.com"
    
    # Verify the database was updated
    db.refresh(test_user)
    assert test_user.name == "Updated Name"
    assert test_user.email == "updated@example.com"


def test_update_user_password(authorized_client, test_user, db):
    # Test updating user password
    response = authorized_client.put(
        "/users/me",
        json={
            "password": "newpassword123"
        }
    )
    assert response.status_code == 200
    
    # Verify the password was updated in the database
    db.refresh(test_user)
    assert verify_password("newpassword123", test_user.hashed_password)


def test_update_user_unauthorized(client):
    # Test updating user without authentication
    response = client.put(
        "/users/me",
        json={
            "name": "Updated Name"
        }
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_delete_user(authorized_client, test_user, db):
    # Test deleting user account
    response = authorized_client.delete("/users/me")
    assert response.status_code == 204
    
    # Verify the user was deleted from the database
    user = db.query(test_user.__class__).filter_by(id=test_user.id).first()
    assert user is None


def test_delete_user_unauthorized(client):
    # Test deleting user without authentication
    response = client.delete("/users/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()
