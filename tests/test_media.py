import pytest
import io
import os
from app.core.config import settings


def test_upload_file(authorized_client, test_user, db, monkeypatch):
    # Create a temporary directory for uploads if it doesn't exist
    os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
    
    # Create a mock file for upload
    file_content = b"test file content"
    file = io.BytesIO(file_content)
    
    # Test uploading a file
    response = authorized_client.post(
        "/v1/media/upload",
        files={"file": ("test_file.txt", file, "text/plain")}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["filename"] == "test_file.txt"
    assert data["file_type"] == "text/plain"
    assert data["file_size"] == len(file_content)
    assert os.path.exists(data["file_path"])
    
    # Clean up the uploaded file
    try:
        os.remove(data["file_path"])
    except:
        pass


def test_upload_file_too_large(authorized_client, monkeypatch):
    # Temporarily set a very small max upload size
    original_max_size = settings.MAX_UPLOAD_SIZE
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 10)  # 10 bytes
    
    # Create a mock file larger than the max size
    file_content = b"x" * 20  # 20 bytes
    file = io.BytesIO(file_content)
    
    # Test uploading a file that's too large
    response = authorized_client.post(
        "/v1/media/upload",
        files={"file": ("large_file.txt", file, "text/plain")}
    )
    
    assert response.status_code == 413
    assert "file too large" in response.json()["detail"].lower()
    
    # Reset the max upload size
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", original_max_size)


def test_upload_file_unauthorized(client):
    # Test uploading a file without authentication
    file_content = b"test file content"
    file = io.BytesIO(file_content)
    
    response = client.post(
        "/v1/media/upload",
        files={"file": ("test_file.txt", file, "text/plain")}
    )
    
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_upload_file_no_file(authorized_client):
    # Test uploading without a file
    response = authorized_client.post("/v1/media/upload")
    
    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data
    # Check that the error is about the missing file
    assert any("file" in error["loc"] for error in data["detail"])
