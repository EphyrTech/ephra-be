from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password


def test_create_access_token():
    # Test creating an access token
    token = create_access_token(subject="test-subject")

    # Decode the token to verify its contents
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "test-subject"
    assert "exp" in payload

    # Verify the expiration time is in the future
    expiration = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert expiration > datetime.now(timezone.utc)


def test_create_access_token_with_expiry():
    # Test creating an access token with a custom expiry
    expires_delta = timedelta(minutes=30)
    token = create_access_token(subject="test-subject", expires_delta=expires_delta)

    # Decode the token to verify its contents
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "test-subject"
    assert "exp" in payload

    # Verify the expiration time is approximately 30 minutes in the future
    expiration = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    assert expiration > now
    assert expiration < now + timedelta(minutes=31)  # Allow for a small margin of error


def test_verify_password():
    # Test password verification
    hashed_password = get_password_hash("testpassword")

    # Correct password should verify
    assert verify_password("testpassword", hashed_password) is True

    # Incorrect password should not verify
    assert verify_password("wrongpassword", hashed_password) is False


def test_get_password_hash():
    # Test password hashing
    password = "testpassword"
    hashed_password = get_password_hash(password)

    # The hash should be different from the original password
    assert hashed_password != password

    # The hash should be a string
    assert isinstance(hashed_password, str)

    # The hash should be verifiable
    assert verify_password(password, hashed_password) is True
