from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_user_from_auth
from app.core.auth_middleware import AuthInfo
from app.core.config import settings
from app.db.models import User, UserRole

# Legacy tests for the old get_current_user function have been removed
# as the function has been replaced with get_current_user_from_auth
# which uses Logto JWT authentication instead of local JWT tokens


# Tests for the new authentication system using get_current_user_from_auth


def test_get_current_user_from_auth_existing_user(db, test_user):
    """Test get_current_user_from_auth with an existing user."""
    # Set up the test user with a logto_user_id
    test_user.logto_user_id = "test-logto-user-id"
    db.add(test_user)
    db.commit()

    # Create a mock AuthInfo
    auth_info = AuthInfo(
        sub="test-logto-user-id", email=test_user.email, name=test_user.name
    )

    # Test the function
    user = get_current_user_from_auth(auth=auth_info, db=db)
    assert user.id == test_user.id
    assert user.email == test_user.email
    assert user.logto_user_id == "test-logto-user-id"


def test_get_current_user_from_auth_new_user(db):
    """Test get_current_user_from_auth with a new user (auto-creation)."""
    auth_info = AuthInfo(
        sub="new-logto-user-id", email="newuser@example.com", name="New User"
    )

    # Test the function - should create a new user
    user = get_current_user_from_auth(auth=auth_info, db=db)
    assert user.email == "newuser@example.com"
    assert user.name == "New User"
    assert user.logto_user_id == "new-logto-user-id"
    assert user.role == UserRole.USER
    assert user.is_active is True


def test_get_current_user_from_auth_missing_email(db):
    """Test get_current_user_from_auth with missing email."""
    auth_info = AuthInfo(
        sub="test-logto-user-id", email=None, name="Test User"  # Missing email
    )

    # Should raise an exception for missing email
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_from_auth(auth=auth_info, db=db)

    assert excinfo.value.status_code == 400
    assert "email is required" in excinfo.value.detail.lower()


def test_get_current_user_from_auth_inactive_user(db, test_user):
    """Test get_current_user_from_auth with an inactive user."""
    # Set up the test user with a logto_user_id and make inactive
    test_user.logto_user_id = "test-logto-user-id"
    test_user.is_active = False
    db.add(test_user)
    db.commit()

    auth_info = AuthInfo(
        sub="test-logto-user-id", email=test_user.email, name=test_user.name
    )

    # Should raise an exception for inactive user
    with pytest.raises(HTTPException) as excinfo:
        get_current_user_from_auth(auth=auth_info, db=db)

    assert excinfo.value.status_code == 400
    assert "inactive user" in excinfo.value.detail.lower()

    # Reset the user to active for other tests
    test_user.is_active = True
    db.add(test_user)
    db.commit()
