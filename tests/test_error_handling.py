import pytest
from fastapi import status


def test_database_error_handling(authorized_client, test_user, force_db_error):
    """Test handling of database errors when creating a journal"""
    response = authorized_client.post(
        "/journals",
        json={
            "title": "Test Journal",
            "content": "This is a test journal entry."
        }
    )
    # Should return a 500 Internal Server Error
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_invalid_token(client):
    """Test handling of invalid authentication token"""
    client.headers = {
        **client.headers,
        "Authorization": "Bearer invalid_token"
    }
    
    response = client.get("/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "could not validate credentials" in response.json()["detail"].lower()


def test_expired_token(client, test_user):
    """Test handling of expired authentication token"""
    from datetime import datetime, timedelta
    from jose import jwt
    from app.core.config import settings
    
    # Create an expired token
    expire = datetime.now(tz=datetime.timezone.utc) - timedelta(minutes=1)
    to_encode = {"exp": expire.timestamp(), "sub": str(test_user.id)}
    expired_token = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {expired_token}"
    }
    
    response = client.get("/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "could not validate credentials" in response.json()["detail"].lower()


def test_inactive_user_authentication(client, inactive_user):
    """Test that inactive users cannot authenticate"""
    response = client.post(
        "/auth/login",
        json={
            "email": inactive_user.email,
            "password": "inactivepassword"
        }
    )
    
    # Should still return a token since we check active status in the get_current_user dependency
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    
    # But using that token should fail
    token = response.json()["access_token"]
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {token}"
    }
    
    response = client.get("/users/me")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive user" in response.json()["detail"].lower()


def test_nonexistent_endpoint(client):
    """Test accessing a non-existent endpoint"""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_method_not_allowed(client):
    """Test using an unsupported HTTP method"""
    response = client.put("/auth/login")  # PUT not supported on login endpoint
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_validation_error(client):
    """Test validation error handling"""
    # Missing required field (password)
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com"
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "field required" in response.json()["detail"][0]["msg"].lower()
    
    # Invalid email format
    response = client.post(
        "/auth/login",
        json={
            "email": "invalid-email",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "valid email" in response.json()["detail"][0]["msg"].lower()


def test_concurrent_database_access(transactional_db, test_user):
    """Test handling of concurrent database access"""
    # Create a new journal in the transaction
    from app.db.models import Journal
    
    journal = Journal(
        user_id=test_user.id,
        title="Transaction Test Journal",
        content="This journal is created in a transaction.",
    )
    transactional_db.add(journal)
    transactional_db.commit()
    
    # The journal should exist in the transaction
    journal_in_transaction = transactional_db.query(Journal).filter(
        Journal.title == "Transaction Test Journal"
    ).first()
    assert journal_in_transaction is not None
    
    # When the transaction is rolled back (at the end of the test),
    # the journal should no longer exist in a new session
    # This is handled by the transactional_db fixture's rollback
