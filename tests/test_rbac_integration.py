"""
Integration tests for RBAC implementation with API endpoints.
"""
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from app.core.auth_middleware import AuthInfo
from app.core.rbac import Scopes


@pytest.fixture
def mock_user_auth():
    """Mock auth for regular user."""
    return AuthInfo(
        sub="user123",
        scopes=[Scopes.JOIN_APPOINTMENTS, Scopes.CREATE_JOURNALS, Scopes.CANCEL_APPOINTMENTS],
        email="user@example.com"
    )


@pytest.fixture
def mock_care_provider_auth():
    """Mock auth for care provider."""
    return AuthInfo(
        sub="care123",
        scopes=[
            Scopes.JOIN_APPOINTMENTS,
            Scopes.CREATE_JOURNALS,
            Scopes.CANCEL_APPOINTMENTS,
            Scopes.CREATE_APPOINTMENTS,
            Scopes.UPDATE_APPOINTMENTS,
            Scopes.VIEW_ALL_APPOINTMENTS,
            Scopes.VIEW_ASSIGNED_USERS,
            Scopes.VIEW_USER_PROFILES,
            Scopes.MANAGE_AVAILABILITY,
            Scopes.VIEW_CARE_DASHBOARD,
            Scopes.VIEW_PATIENT_JOURNALS,
        ],
        email="care@example.com"
    )


@pytest.fixture
def mock_admin_auth():
    """Mock auth for admin."""
    return AuthInfo(
        sub="admin123",
        scopes=[
            # All care provider scopes plus admin scopes
            Scopes.JOIN_APPOINTMENTS,
            Scopes.CREATE_JOURNALS,
            Scopes.CANCEL_APPOINTMENTS,
            Scopes.CREATE_APPOINTMENTS,
            Scopes.UPDATE_APPOINTMENTS,
            Scopes.VIEW_ALL_APPOINTMENTS,
            Scopes.VIEW_ASSIGNED_USERS,
            Scopes.VIEW_USER_PROFILES,
            Scopes.MANAGE_AVAILABILITY,
            Scopes.VIEW_CARE_DASHBOARD,
            Scopes.VIEW_PATIENT_JOURNALS,
            Scopes.ACCESS_ADMIN_PANEL,
            Scopes.MANAGE_ALL_USERS,
            Scopes.MANAGE_USER_ASSIGNMENTS,
            Scopes.VIEW_SYSTEM_STATS,
        ],
        email="admin@example.com"
    )


class TestAppointmentEndpointsRBAC:
    """Test RBAC for appointment endpoints."""
    
    @patch('app.api.appointments.verify_access_token')
    @patch('app.api.appointments.get_current_user_from_auth')
    def test_create_appointment_with_valid_scope(self, mock_get_user, mock_verify, client, mock_care_provider_auth):
        """Test creating appointment with valid scope."""
        mock_verify.return_value = mock_care_provider_auth
        mock_get_user.return_value = Mock(id="care123")
        
        with patch('app.api.appointments.AppointmentService') as mock_service:
            mock_service.return_value.create_appointment.return_value = {
                "id": "apt123",
                "user_id": "user456",
                "care_provider_id": "care123"
            }
            
            response = client.post(
                "/v1/appointments/",
                json={
                    "user_id": "user456",
                    "scheduled_at": "2024-01-15T10:00:00Z",
                    "duration_minutes": 60
                },
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 201
    
    @patch('app.api.appointments.verify_access_token')
    def test_create_appointment_without_scope(self, mock_verify, client, mock_user_auth):
        """Test creating appointment without required scope."""
        # User doesn't have create:appointments scope
        mock_verify.return_value = mock_user_auth
        
        response = client.post(
            "/v1/appointments/",
            json={
                "user_id": "user456",
                "scheduled_at": "2024-01-15T10:00:00Z",
                "duration_minutes": 60
            },
            headers={"Authorization": "Bearer valid_token"}
        )
        
        assert response.status_code == 403
        assert "Permission required to create appointments" in response.json()["detail"]
    
    @patch('app.api.appointments.verify_access_token')
    @patch('app.api.appointments.get_current_user_from_auth')
    def test_cancel_appointment_with_valid_scope(self, mock_get_user, mock_verify, client, mock_user_auth):
        """Test canceling appointment with valid scope."""
        mock_verify.return_value = mock_user_auth
        mock_get_user.return_value = Mock(id="user123")
        
        with patch('app.api.appointments.AppointmentService') as mock_service:
            mock_service.return_value.cancel_appointment_with_email.return_value = None
            
            response = client.delete(
                "/v1/appointments/apt123",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 204


class TestAdminEndpointsRBAC:
    """Test RBAC for admin endpoints."""
    
    @patch('app.api.admin.require_manage_all_users')
    def test_get_all_users_with_admin_scope(self, mock_require, client, mock_admin_auth):
        """Test getting all users with admin scope."""
        mock_require.return_value = mock_admin_auth
        
        with patch('app.api.admin.get_db') as mock_db:
            mock_db.return_value.query.return_value.offset.return_value.limit.return_value.all.return_value = []
            
            response = client.get(
                "/v1/admin/users",
                headers={"Authorization": "Bearer admin_token"}
            )
            
            assert response.status_code == 200
    
    @patch('app.api.admin.require_manage_all_users')
    def test_get_all_users_without_admin_scope(self, mock_require, client):
        """Test getting all users without admin scope."""
        from fastapi import HTTPException
        mock_require.side_effect = HTTPException(status_code=403, detail="Insufficient permissions")
        
        response = client.get(
            "/v1/admin/users",
            headers={"Authorization": "Bearer user_token"}
        )
        
        assert response.status_code == 403


class TestJournalEndpointsRBAC:
    """Test RBAC for journal endpoints."""
    
    @patch('app.api.journals.verify_access_token')
    @patch('app.api.journals.get_current_user_from_auth')
    def test_create_journal_with_valid_scope(self, mock_get_user, mock_verify, client, mock_user_auth):
        """Test creating journal with valid scope."""
        mock_verify.return_value = mock_user_auth
        mock_get_user.return_value = Mock(id="user123")
        
        with patch('app.api.journals.get_db') as mock_db:
            mock_session = Mock()
            mock_db.return_value = mock_session
            
            response = client.post(
                "/v1/journals/",
                json={
                    "title": "My Journal Entry",
                    "content": "Today was a good day"
                },
                headers={"Authorization": "Bearer valid_token"}
            )
            
            # Should not get 403 (scope validation passed)
            assert response.status_code != 403
    
    @patch('app.api.journals.verify_access_token')
    @patch('app.api.journals.has_scope')
    @patch('app.api.journals.get_current_user_from_auth')
    def test_get_journals_care_provider_scope(self, mock_get_user, mock_has_scope, mock_verify, client, mock_care_provider_auth):
        """Test getting journals with care provider scope."""
        mock_verify.return_value = mock_care_provider_auth
        mock_get_user.return_value = Mock(id="care123")
        mock_has_scope.return_value = True  # Has view:patient-journals scope
        
        with patch('app.api.journals.get_db') as mock_db:
            mock_session = Mock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.offset.return_value.limit.return_value.all.return_value = []
            
            response = client.get(
                "/v1/journals/",
                headers={"Authorization": "Bearer care_token"}
            )
            
            assert response.status_code == 200


class TestCareProviderEndpointsRBAC:
    """Test RBAC for care provider endpoints."""
    
    @patch('app.api.care_providers.require_manage_availability')
    @patch('app.api.care_providers.get_current_user_from_auth')
    def test_create_availability_with_valid_scope(self, mock_get_user, mock_require, client, mock_care_provider_auth):
        """Test creating availability with valid scope."""
        mock_require.return_value = mock_care_provider_auth
        mock_get_user.return_value = Mock(id="care123")
        
        with patch('app.api.care_providers.CareProviderService') as mock_service:
            mock_service.return_value.create_my_availability.return_value = {
                "id": "avail123",
                "day_of_week": 1,
                "start_time": "09:00",
                "end_time": "17:00"
            }
            
            response = client.post(
                "/v1/care-providers/me/availability",
                json={
                    "day_of_week": 1,
                    "start_time": "09:00",
                    "end_time": "17:00"
                },
                headers={"Authorization": "Bearer care_token"}
            )
            
            assert response.status_code == 201
    
    @patch('app.api.care_providers.require_view_care_dashboard')
    @patch('app.api.care_providers.get_current_user_from_auth')
    def test_get_care_profile_with_valid_scope(self, mock_get_user, mock_require, client, mock_care_provider_auth):
        """Test getting care provider profile with valid scope."""
        mock_require.return_value = mock_care_provider_auth
        mock_get_user.return_value = Mock(id="care123")
        
        with patch('app.api.care_providers.CareProviderService') as mock_service:
            mock_service.return_value.get_my_profile.return_value = {
                "id": "profile123",
                "specialty": "mental",
                "bio": "Experienced therapist"
            }
            
            response = client.get(
                "/v1/care-providers/me",
                headers={"Authorization": "Bearer care_token"}
            )
            
            assert response.status_code == 200


class TestScopeValidationFlow:
    """Test the complete scope validation flow."""
    
    def test_jwt_scope_extraction_and_validation(self):
        """Test JWT scope extraction and validation flow."""
        from app.core.auth_middleware import create_auth_info, verify_payload
        from app.core.rbac import has_scope
        
        # Simulate JWT payload with scopes
        payload = {
            "sub": "user123",
            "aud": ["https://api.ephra.com"],
            "scope": "create:appointments view:assigned-users manage:availability",
            "email": "test@example.com",
            "exp": 9999999999  # Far future
        }
        
        # Verify payload (should not raise exception)
        with patch('app.core.auth_middleware.settings') as mock_settings:
            mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"
            verify_payload(payload)
        
        # Create auth info
        auth = create_auth_info(payload)
        
        # Test scope checking
        assert has_scope(auth, "create:appointments") is True
        assert has_scope(auth, "view:assigned-users") is True
        assert has_scope(auth, "manage:availability") is True
        assert has_scope(auth, "manage:all-users") is False
    
    def test_role_based_scope_assignment(self):
        """Test that roles have correct scopes assigned."""
        from app.core.rbac import RoleScopes, get_user_role_from_scopes
        
        # Test user role
        user_role = get_user_role_from_scopes(RoleScopes.USER)
        assert user_role == "user"
        
        # Test care provider role
        care_role = get_user_role_from_scopes(RoleScopes.CARE_PROVIDER)
        assert care_role == "care_provider"
        
        # Test admin role
        admin_role = get_user_role_from_scopes(RoleScopes.ADMIN)
        assert admin_role == "admin"


if __name__ == "__main__":
    pytest.main([__file__])
