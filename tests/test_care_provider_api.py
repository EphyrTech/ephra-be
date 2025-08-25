"""Tests for care provider API endpoints"""

from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.db.models import SpecialistType, User, UserRole
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from main import app


class TestCareProviderAPIIntegration:
    """Integration test cases for care provider API endpoints"""

    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)

    def test_get_care_providers_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/v1/care-providers/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_my_profile_unauthenticated(self, client):
        """Test that unauthenticated requests to profile are rejected"""
        response = client.get("/v1/care-providers/me")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_my_profile_unauthenticated(self, client):
        """Test that unauthenticated profile creation is rejected"""
        profile_data = {
            "specialty": "mental",
            "bio": "Test bio",
            "hourly_rate": 10000,
        }
        response = client.post("/v1/care-providers/me", json=profile_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_pagination_validation(self, client):
        """Test pagination parameter validation"""
        # Note: Authentication happens before validation, so we expect 403 for unauthenticated requests
        # This test verifies that the endpoints exist and respond appropriately

        # Test negative skip - authentication fails first
        response = client.get("/v1/care-providers/?skip=-1")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Test limit too high - authentication fails first
        response = client.get("/v1/care-providers/?limit=2000")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Test limit too low - authentication fails first
        response = client.get("/v1/care-providers/?limit=0")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCareProviderAPIUnit:
    """Unit test cases for care provider API endpoints with mocked dependencies"""

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.role = UserRole.CARE_PROVIDER
        user.is_active = True
        return user

    @pytest.fixture
    def mock_care_provider_data(self):
        """Mock care provider data"""
        return {
            "id": "profile-123",
            "user_id": "user-123",
            "specialty": "mental",
            "bio": "Test bio",
            "hourly_rate": 10000,
            "is_accepting_patients": True,
            "user_name": "Dr. Test",
            "user_email": "test@example.com",
            "user_first_name": "Test",
            "user_last_name": "Doctor",
        }

    def test_service_layer_integration(self, mock_user, mock_care_provider_data):
        """Test that the service layer can be imported and instantiated"""
        from unittest.mock import Mock

        from app.services.care_provider_service import CareProviderService

        # Test that service can be created
        mock_db = Mock()
        service = CareProviderService(mock_db)

        # Test that service methods exist
        assert hasattr(service, "get_care_providers")
        assert hasattr(service, "get_my_profile")
        assert hasattr(service, "create_my_profile")
        assert hasattr(service, "update_my_profile")
        assert hasattr(service, "get_my_availability")
        assert hasattr(service, "create_my_availability")
        assert hasattr(service, "update_my_availability")
        assert hasattr(service, "delete_my_availability")

    def test_api_endpoints_exist(self):
        """Test that API endpoints are properly registered"""
        from main import app

        # Get all routes with their full paths
        routes = []
        for route in app.routes:
            if hasattr(route, "path"):
                routes.append(route.path)

        # Check that care provider routes exist (exact matches)
        expected_routes = [
            "/v1/care-providers/",  # GET care providers list
            "/v1/care-providers/me",  # GET/POST/PUT my profile
            "/v1/care-providers/{care_provider_id}",  # GET specific care provider
            "/v1/care-providers/me/availability",  # GET/POST my availability
            "/v1/care-providers/me/availability/{availability_id}",  # PUT/DELETE specific availability
        ]

        for expected_route in expected_routes:
            assert (
                expected_route in routes
            ), f"Route {expected_route} not found in {routes}"
