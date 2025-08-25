import pytest
from fastapi import status


def test_google_authentication(client, mock_google_auth):
    """Test Google authentication with mocked Google service"""
    response = client.post(
        "/v1/auth/google",
        json={
            "token": "mock_google_token"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_password_reset_email(client, test_user, mock_email_service):
    """Test password reset email sending with mocked email service"""
    response = client.post(
        "/v1/auth/reset-password",
        json={
            "email": test_user.email
        }
    )
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "password reset email sent" in response.json()["message"].lower()
    
    # Check that an email was sent to the user
    assert len(mock_email_service) == 1
    assert mock_email_service[0]["to"] == test_user.email
    assert "reset" in mock_email_service[0]["subject"].lower()


def test_environment_variables(mock_env_vars):
    """Test accessing environment variables"""
    import os
    
    assert os.getenv("TEST_MODE") == "True"
    assert os.getenv("TEST_SECRET_KEY") == "test_secret_key"


def test_file_upload_with_mock_file(authorized_client, test_user, mock_file):
    """Test file upload with a mock file"""
    import os
    from app.core.config import settings
    
    # Create uploads directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
    
    response = authorized_client.post(
        "/v1/media/upload",
        files={
            "file": (
                mock_file["filename"],
                mock_file["file"],
                mock_file["content_type"]
            )
        }
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["filename"] == mock_file["filename"]
    assert data["file_type"] == mock_file["content_type"]
    assert data["file_size"] == mock_file["size"]
    
    # Clean up the uploaded file
    try:
        os.remove(data["file_path"])
    except:
        pass
