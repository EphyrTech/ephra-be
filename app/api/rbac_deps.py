"""
FastAPI dependencies for Role-Based Access Control (RBAC).
These dependencies can be used to protect API endpoints with scope-based authorization.
"""
from typing import List, Callable
from fastapi import Depends, HTTPException
from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.rbac import Scopes, require_scope, require_any_scope, require_all_scopes


def require_scope_dep(required_scope: str, error_message: str = None) -> Callable:
    """
    Create a FastAPI dependency that requires a specific scope.
    
    Args:
        required_scope: The scope to require
        error_message: Custom error message (optional)
        
    Returns:
        FastAPI dependency function
    """
    def dependency(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        require_scope(auth, required_scope, error_message)
        return auth
    
    return dependency


def require_any_scope_dep(required_scopes: List[str], error_message: str = None) -> Callable:
    """
    Create a FastAPI dependency that requires any of the specified scopes.
    
    Args:
        required_scopes: List of scopes, user needs at least one
        error_message: Custom error message (optional)
        
    Returns:
        FastAPI dependency function
    """
    def dependency(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        require_any_scope(auth, required_scopes, error_message)
        return auth
    
    return dependency


def require_all_scopes_dep(required_scopes: List[str], error_message: str = None) -> Callable:
    """
    Create a FastAPI dependency that requires all of the specified scopes.
    
    Args:
        required_scopes: List of scopes, user needs all of them
        error_message: Custom error message (optional)
        
    Returns:
        FastAPI dependency function
    """
    def dependency(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        require_all_scopes(auth, required_scopes, error_message)
        return auth
    
    return dependency


# Pre-defined dependencies for common permission patterns

# Appointment Management Dependencies
require_join_appointments = require_scope_dep(
    Scopes.JOIN_APPOINTMENTS,
    "Permission required to join appointments"
)

require_create_appointments = require_scope_dep(
    Scopes.CREATE_APPOINTMENTS,
    "Permission required to create appointments"
)

require_update_appointments = require_scope_dep(
    Scopes.UPDATE_APPOINTMENTS,
    "Permission required to update appointments"
)

require_cancel_appointments = require_scope_dep(
    Scopes.CANCEL_APPOINTMENTS,
    "Permission required to cancel appointments"
)

require_view_all_appointments = require_scope_dep(
    Scopes.VIEW_ALL_APPOINTMENTS,
    "Permission required to view all appointments"
)

# User Management Dependencies
require_view_assigned_users = require_scope_dep(
    Scopes.VIEW_ASSIGNED_USERS,
    "Permission required to view assigned users"
)

require_manage_user_assignments = require_scope_dep(
    Scopes.MANAGE_USER_ASSIGNMENTS,
    "Permission required to manage user assignments"
)

require_view_user_profiles = require_scope_dep(
    Scopes.VIEW_USER_PROFILES,
    "Permission required to view user profiles"
)

# Care Provider Dependencies
require_manage_availability = require_scope_dep(
    Scopes.MANAGE_AVAILABILITY,
    "Permission required to manage availability"
)

require_view_care_dashboard = require_scope_dep(
    Scopes.VIEW_CARE_DASHBOARD,
    "Permission required to access care dashboard"
)

# Journal Dependencies
require_create_journals = require_scope_dep(
    Scopes.CREATE_JOURNALS,
    "Permission required to create journals"
)

require_view_patient_journals = require_scope_dep(
    Scopes.VIEW_PATIENT_JOURNALS,
    "Permission required to view patient journals"
)

# Admin Dependencies
require_access_admin_panel = require_scope_dep(
    Scopes.ACCESS_ADMIN_PANEL,
    "Admin access required"
)

require_manage_all_users = require_scope_dep(
    Scopes.MANAGE_ALL_USERS,
    "Permission required to manage all users"
)

require_view_system_stats = require_scope_dep(
    Scopes.VIEW_SYSTEM_STATS,
    "Permission required to view system statistics"
)

# Combined Dependencies for common patterns

# Care provider or admin access
require_care_provider_or_admin = require_any_scope_dep(
    [Scopes.CREATE_APPOINTMENTS, Scopes.MANAGE_ALL_USERS],
    "Care provider or admin access required"
)

# Admin-only access
require_admin_access = require_scope_dep(
    Scopes.MANAGE_ALL_USERS,
    "Administrator access required"
)

# Appointment management (create or update)
require_appointment_management = require_any_scope_dep(
    [Scopes.CREATE_APPOINTMENTS, Scopes.UPDATE_APPOINTMENTS],
    "Permission required to manage appointments"
)

# Journal access (create own or view patient journals)
require_journal_access = require_any_scope_dep(
    [Scopes.CREATE_JOURNALS, Scopes.VIEW_PATIENT_JOURNALS],
    "Permission required to access journals"
)


def require_user_access(target_user_id: str) -> Callable:
    """
    Create a dependency that checks if user can access specific user data.
    This implements ownership-based access control combined with RBAC.
    
    Args:
        target_user_id: ID of the user whose data is being accessed
        
    Returns:
        FastAPI dependency function
    """
    def dependency(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        # Users can access their own data
        if auth.sub == target_user_id:
            return auth
        
        # Care providers can access assigned users
        if auth.has_scope(Scopes.VIEW_ASSIGNED_USERS):
            return auth
        
        # Admins can access all users
        if auth.has_scope(Scopes.MANAGE_ALL_USERS):
            return auth
        
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to access this user's data"
        )
    
    return dependency


def require_appointment_access_for_user(target_user_id: str) -> Callable:
    """
    Create a dependency that checks if user can manage appointments for a specific user.
    
    Args:
        target_user_id: ID of the user whose appointments are being managed
        
    Returns:
        FastAPI dependency function
    """
    def dependency(auth: AuthInfo = Depends(verify_access_token)) -> AuthInfo:
        # Users can manage their own appointments if they have create scope
        if auth.sub == target_user_id and auth.has_scope(Scopes.CREATE_APPOINTMENTS):
            return auth
        
        # Care providers can manage appointments for assigned users
        if (auth.has_scope(Scopes.CREATE_APPOINTMENTS) and 
            auth.has_scope(Scopes.VIEW_ASSIGNED_USERS)):
            return auth
        
        # Admins can manage all appointments
        if (auth.has_scope(Scopes.CREATE_APPOINTMENTS) and 
            auth.has_scope(Scopes.MANAGE_ALL_USERS)):
            return auth
        
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to manage appointments for this user"
        )
    
    return dependency
