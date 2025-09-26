"""
Tests for Role-Based Access Control (RBAC) implementation.
"""
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.rbac_deps import (
    require_all_scopes_dep,
    require_any_scope_dep,
    require_create_appointments,
    require_manage_all_users,
    require_scope_dep,
    require_view_patient_journals,
)
from app.core.auth_middleware import AuthInfo
from app.core.rbac import (
    RoleScopes,
    Scopes,
    can_access_user_data,
    can_manage_appointments_for_user,
    get_user_role_from_scopes,
    has_all_scopes,
    has_any_scope,
    has_scope,
    require_all_scopes,
    require_any_scope,
    require_scope,
)


class TestScopeDefinitions:
    """Test scope definitions and role mappings."""
    
    def test_scope_constants(self):
        """Test that all scope constants are defined."""
        assert Scopes.JOIN_APPOINTMENTS == "join:appointments"
        assert Scopes.CREATE_APPOINTMENTS == "create:appointments"
        assert Scopes.UPDATE_APPOINTMENTS == "update:appointments"
        assert Scopes.CANCEL_APPOINTMENTS == "cancel:appointments"
        assert Scopes.VIEW_ALL_APPOINTMENTS == "view:all-appointments"
        assert Scopes.VIEW_ASSIGNED_USERS == "view:assigned-users"
        assert Scopes.MANAGE_USER_ASSIGNMENTS == "manage:user-assignments"
        assert Scopes.VIEW_USER_PROFILES == "view:user-profiles"
        assert Scopes.MANAGE_AVAILABILITY == "manage:availability"
        assert Scopes.VIEW_CARE_DASHBOARD == "view:care-dashboard"
        assert Scopes.CREATE_JOURNALS == "create:journals"
        assert Scopes.VIEW_PATIENT_JOURNALS == "view:patient-journals"
        assert Scopes.ACCESS_ADMIN_PANEL == "access:admin-panel"
        assert Scopes.MANAGE_ALL_USERS == "manage:all-users"
        assert Scopes.VIEW_SYSTEM_STATS == "view:system-stats"
    
    def test_role_scopes(self):
        """Test that role scope mappings are correct."""
        # User role should have basic scopes
        assert Scopes.JOIN_APPOINTMENTS in RoleScopes.USER
        assert Scopes.CREATE_JOURNALS in RoleScopes.USER
        assert Scopes.CANCEL_APPOINTMENTS in RoleScopes.USER
        assert len(RoleScopes.USER) == 3
        
        # Care provider should have user scopes plus additional ones
        assert all(scope in RoleScopes.CARE_PROVIDER for scope in RoleScopes.USER)
        assert Scopes.CREATE_APPOINTMENTS in RoleScopes.CARE_PROVIDER
        assert Scopes.VIEW_ASSIGNED_USERS in RoleScopes.CARE_PROVIDER
        assert Scopes.VIEW_PATIENT_JOURNALS in RoleScopes.CARE_PROVIDER
        
        # Admin should have all care provider scopes plus admin ones
        assert all(scope in RoleScopes.ADMIN for scope in RoleScopes.CARE_PROVIDER)
        assert Scopes.MANAGE_ALL_USERS in RoleScopes.ADMIN
        assert Scopes.ACCESS_ADMIN_PANEL in RoleScopes.ADMIN


class TestAuthInfo:
    """Test AuthInfo class functionality."""
    
    def test_auth_info_creation(self):
        """Test AuthInfo object creation."""
        auth = AuthInfo(
            sub="user123",
            scopes=["create:appointments", "view:assigned-users"],
            email="test@example.com"
        )
        assert auth.sub == "user123"
        assert auth.scopes == ["create:appointments", "view:assigned-users"]
        assert auth.email == "test@example.com"
    
    def test_has_scope(self):
        """Test has_scope method."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments", "view:assigned-users"])
        assert auth.has_scope("create:appointments") is True
        assert auth.has_scope("manage:all-users") is False
    
    def test_has_any_scope(self):
        """Test has_any_scope method."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments", "view:assigned-users"])
        assert auth.has_any_scope(["create:appointments", "manage:all-users"]) is True
        assert auth.has_any_scope(["manage:all-users", "access:admin-panel"]) is False
    
    def test_has_all_scopes(self):
        """Test has_all_scopes method."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments", "view:assigned-users"])
        assert auth.has_all_scopes(["create:appointments", "view:assigned-users"]) is True
        assert auth.has_all_scopes(["create:appointments", "manage:all-users"]) is False


class TestPermissionFunctions:
    """Test permission checking functions."""
    
    def test_has_scope_function(self):
        """Test has_scope function."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        assert has_scope(auth, "create:appointments") is True
        assert has_scope(auth, "manage:all-users") is False
    
    def test_require_scope_success(self):
        """Test require_scope with valid scope."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        # Should not raise exception
        require_scope(auth, "create:appointments")
    
    def test_require_scope_failure(self):
        """Test require_scope with invalid scope."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        with pytest.raises(HTTPException) as exc_info:
            require_scope(auth, "manage:all-users")
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
    
    def test_require_any_scope_success(self):
        """Test require_any_scope with valid scopes."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        # Should not raise exception
        require_any_scope(auth, ["create:appointments", "manage:all-users"])
    
    def test_require_any_scope_failure(self):
        """Test require_any_scope with no valid scopes."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        with pytest.raises(HTTPException) as exc_info:
            require_any_scope(auth, ["manage:all-users", "access:admin-panel"])
        assert exc_info.value.status_code == 403
    
    def test_require_all_scopes_success(self):
        """Test require_all_scopes with all valid scopes."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments", "view:assigned-users"])
        # Should not raise exception
        require_all_scopes(auth, ["create:appointments", "view:assigned-users"])
    
    def test_require_all_scopes_failure(self):
        """Test require_all_scopes with missing scopes."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        with pytest.raises(HTTPException) as exc_info:
            require_all_scopes(auth, ["create:appointments", "manage:all-users"])
        assert exc_info.value.status_code == 403
        assert "Missing scopes" in str(exc_info.value.detail)


class TestAccessControlLogic:
    """Test complex access control logic."""
    
    def test_can_access_user_data_own_data(self):
        """Test user can access their own data."""
        auth = AuthInfo(sub="user123", scopes=["create:journals"])
        assert can_access_user_data(auth, "user123") is True
    
    def test_can_access_user_data_care_provider(self):
        """Test care provider can access assigned user data."""
        auth = AuthInfo(sub="care123", scopes=["view:assigned-users"])
        assert can_access_user_data(auth, "user456") is True
    
    def test_can_access_user_data_admin(self):
        """Test admin can access any user data."""
        auth = AuthInfo(sub="admin123", scopes=["manage:all-users"])
        assert can_access_user_data(auth, "user456") is True
    
    def test_can_access_user_data_denied(self):
        """Test access denied for unauthorized user."""
        auth = AuthInfo(sub="user123", scopes=["create:journals"])
        assert can_access_user_data(auth, "user456") is False
    
    def test_can_manage_appointments_for_user_own(self):
        """Test user can manage their own appointments."""
        auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        assert can_manage_appointments_for_user(auth, "user123") is True
    
    def test_can_manage_appointments_care_provider(self):
        """Test care provider can manage appointments for assigned users."""
        auth = AuthInfo(sub="care123", scopes=["create:appointments", "view:assigned-users"])
        assert can_manage_appointments_for_user(auth, "user456") is True
    
    def test_can_manage_appointments_admin(self):
        """Test admin can manage all appointments."""
        auth = AuthInfo(sub="admin123", scopes=["create:appointments", "manage:all-users"])
        assert can_manage_appointments_for_user(auth, "user456") is True
    
    def test_get_user_role_from_scopes(self):
        """Test role determination from scopes."""
        admin_scopes = ["manage:all-users", "create:appointments"]
        care_scopes = ["create:appointments", "view:assigned-users"]
        user_scopes = ["create:journals", "join:appointments"]
        
        assert get_user_role_from_scopes(admin_scopes) == "admin"
        assert get_user_role_from_scopes(care_scopes) == "care_provider"
        assert get_user_role_from_scopes(user_scopes) == "user"


class TestRBACDependencies:
    """Test FastAPI RBAC dependencies."""
    
    @patch('app.api.rbac_deps.verify_access_token')
    def test_require_scope_dependency(self, mock_verify):
        """Test scope requirement dependency."""
        # Mock auth with required scope
        mock_auth = AuthInfo(sub="user123", scopes=["create:appointments"])
        mock_verify.return_value = mock_auth
        
        # Create dependency
        dep = require_scope_dep("create:appointments")
        
        # Should return auth info without exception
        result = dep(mock_auth)
        assert result == mock_auth
    
    @patch('app.api.rbac_deps.verify_access_token')
    def test_require_scope_dependency_failure(self, mock_verify):
        """Test scope requirement dependency failure."""
        # Mock auth without required scope
        mock_auth = AuthInfo(sub="user123", scopes=["create:journals"])
        mock_verify.return_value = mock_auth
        
        # Create dependency
        dep = require_scope_dep("create:appointments")
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            dep(mock_auth)
        assert exc_info.value.status_code == 403
    
    def test_predefined_dependencies_exist(self):
        """Test that predefined dependencies are available."""
        # Test that key dependencies are defined
        assert require_create_appointments is not None
        assert require_manage_all_users is not None
        assert require_view_patient_journals is not None


class TestJWTValidation:
    """Test JWT validation with RBAC."""

    @patch('app.core.auth_middleware.settings')
    def test_client_id_validation(self, mock_settings):
        """Test JWT client_id validation."""
        from app.core.auth_middleware import AuthorizationError, verify_payload

        mock_settings.LOGTO_APP_ID = "test-app-id"
        mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"

        # Valid payload with correct client_id
        valid_payload = {
            "sub": "user123",
            "client_id": "test-app-id",
            "aud": ["https://api.ephra.com"],
            "scope": "create:appointments view:assigned-users"
        }

        # Should not raise exception
        verify_payload(valid_payload)

        # Invalid payload with wrong client_id
        invalid_payload = {
            "sub": "user123",
            "client_id": "wrong-app-id",
            "aud": ["https://api.ephra.com"],
            "scope": "create:appointments"
        }

        # Should raise exception
        with pytest.raises(AuthorizationError) as exc_info:
            verify_payload(invalid_payload)
        assert "Invalid client_id" in str(exc_info.value.message)

    @patch('app.core.auth_middleware.settings')
    def test_audience_validation(self, mock_settings):
        """Test JWT audience validation."""
        from app.core.auth_middleware import AuthorizationError, verify_payload

        mock_settings.LOGTO_APP_ID = "test-app-id"
        mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"

        # Valid payload with correct audience
        valid_payload = {
            "sub": "user123",
            "client_id": "test-app-id",
            "aud": ["https://api.ephra.com"],
            "scope": "create:appointments view:assigned-users"
        }

        # Should not raise exception
        verify_payload(valid_payload)

        # Invalid payload with wrong audience
        invalid_payload = {
            "sub": "user123",
            "client_id": "test-app-id",
            "aud": ["https://wrong-api.com"],
            "scope": "create:appointments"
        }

        # Should raise exception
        with pytest.raises(AuthorizationError) as exc_info:
            verify_payload(invalid_payload)
        assert "Invalid audience" in str(exc_info.value.message)
    
    def test_scope_extraction(self):
        """Test scope extraction from JWT payload."""
        from app.core.auth_middleware import create_auth_info
        
        payload = {
            "sub": "user123",
            "scope": "create:appointments view:assigned-users manage:availability",
            "email": "test@example.com"
        }
        
        auth = create_auth_info(payload)
        
        assert auth.sub == "user123"
        assert auth.email == "test@example.com"
        assert "create:appointments" in auth.scopes
        assert "view:assigned-users" in auth.scopes
        assert "manage:availability" in auth.scopes
        assert len(auth.scopes) == 3
    
    def test_empty_scope_handling(self):
        """Test handling of empty or missing scopes."""
        from app.core.auth_middleware import create_auth_info
        
        payload = {
            "sub": "user123",
            "email": "test@example.com"
        }
        
        auth = create_auth_info(payload)
        
        assert auth.sub == "user123"
        assert auth.scopes == []
        assert not auth.has_scope("any:scope")


class TestLogtoConfiguration:
    """Test Logto configuration validation."""

    @patch('app.core.auth_middleware.settings')
    def test_validate_logto_config_success(self, mock_settings):
        """Test successful Logto configuration validation."""
        from app.core.auth_middleware import validate_logto_config

        mock_settings.LOGTO_ENDPOINT = "https://logto.example.com"
        mock_settings.LOGTO_APP_ID = "test-app-id"
        mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"

        assert validate_logto_config() is True

    @patch('app.core.auth_middleware.settings')
    def test_validate_logto_config_missing_endpoint(self, mock_settings):
        """Test Logto configuration validation with missing endpoint."""
        from app.core.auth_middleware import validate_logto_config

        mock_settings.LOGTO_ENDPOINT = ""
        mock_settings.LOGTO_APP_ID = "test-app-id"
        mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"

        assert validate_logto_config() is False

    @patch('app.core.auth_middleware.settings')
    def test_validate_logto_config_missing_app_id(self, mock_settings):
        """Test Logto configuration validation with missing app ID."""
        from app.core.auth_middleware import validate_logto_config

        mock_settings.LOGTO_ENDPOINT = "https://logto.example.com"
        mock_settings.LOGTO_APP_ID = ""
        mock_settings.LOGTO_API_RESOURCE = "https://api.ephra.com"

        assert validate_logto_config() is False

    @patch('app.core.auth_middleware.settings')
    def test_validate_logto_config_missing_api_resource(self, mock_settings):
        """Test Logto configuration validation with missing API resource."""
        from app.core.auth_middleware import validate_logto_config

        mock_settings.LOGTO_ENDPOINT = "https://logto.example.com"
        mock_settings.LOGTO_APP_ID = "test-app-id"
        mock_settings.LOGTO_API_RESOURCE = ""

        assert validate_logto_config() is False


if __name__ == "__main__":
    pytest.main([__file__])
