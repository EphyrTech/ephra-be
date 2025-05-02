import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_user
from app.core.config import settings


def test_get_current_user_valid_token(db, test_user, test_user_token):
    # Create a mock token
    token = test_user_token
    
    # Test the get_current_user dependency with a valid token
    user = get_current_user(db=db, token=token)
    assert user.id == test_user.id
    assert user.email == test_user.email


def test_get_current_user_invalid_token(db):
    # Test with an invalid token
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(db=db, token="invalid-token")
    
    assert excinfo.value.status_code == 401
    assert "could not validate credentials" in excinfo.value.detail.lower()


def test_get_current_user_expired_token(db, test_user):
    # Create an expired token
    from datetime import datetime, timedelta
    
    expire = datetime.utcnow() - timedelta(minutes=1)  # Token expired 1 minute ago
    to_encode = {"exp": expire, "sub": str(test_user.id)}
    expired_token = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    
    # Test with an expired token
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(db=db, token=expired_token)
    
    assert excinfo.value.status_code == 401
    assert "could not validate credentials" in excinfo.value.detail.lower()


def test_get_current_user_nonexistent_user(db, test_user):
    # Create a token for a non-existent user
    from datetime import datetime, timedelta
    
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"exp": expire, "sub": "nonexistent-user-id"}
    token = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    
    # Test with a token for a non-existent user
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(db=db, token=token)
    
    assert excinfo.value.status_code == 404
    assert "user not found" in excinfo.value.detail.lower()


def test_get_current_user_inactive_user(db, test_user, test_user_token):
    # Make the test user inactive
    test_user.is_active = False
    db.add(test_user)
    db.commit()
    
    # Test with a token for an inactive user
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(db=db, token=test_user_token)
    
    assert excinfo.value.status_code == 400
    assert "inactive user" in excinfo.value.detail.lower()
    
    # Reset the user to active for other tests
    test_user.is_active = True
    db.add(test_user)
    db.commit()
