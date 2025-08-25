import pytest
from fastapi.testclient import TestClient

from main import app


def test_root_endpoint():
    # Test the root endpoint
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to Mental Health API"}


def test_docs_endpoint():
    # Test that the OpenAPI docs are accessible
    with TestClient(app) as client:
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_openapi_schema():
    # Test that the OpenAPI schema is accessible
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        # Check basic structure of the schema
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

        # Check that our API endpoints are in the schema
        assert "/v1/auth/register" in schema["paths"]
        assert "/v1/auth/login" in schema["paths"]
        assert "/v1/users/me" in schema["paths"]
        assert "/v1/journals/" in schema["paths"]
        assert "/v1/appointments/" in schema["paths"]
        assert "/v1/care-providers/" in schema["paths"]
        assert "/v1/media/upload" in schema["paths"]
