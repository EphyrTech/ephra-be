"""
Role-Based Access Control (RBAC) utilities for Logto integration.
This module provides permission checking functions and scope definitions.
"""
from typing import List, Optional
from fastapi import HTTPException, Request
from app.schemas.auth import AuthInfo


# Define all available scopes in the system
class Scopes:
    """Centralized scope definitions for Ephra API."""
    
    # Appointment Management
    JOIN_APPOINTMENTS = "join:appointments"
    CREATE_APPOINTMENTS = "create:appointments"
    UPDATE_APPOINTMENTS = "update:appointments"
    CANCEL_APPOINTMENTS = "cancel:appointments"
    VIEW_ALL_APPOINTMENTS = "view:all-appointments"
    
    # User Management
    VIEW_ASSIGNED_USERS = "view:assigned-users"
    MANAGE_USER_ASSIGNMENTS = "manage:user-assignments"
    VIEW_USER_PROFILES = "view:user-profiles"
    
    # Care Provider Features
    MANAGE_AVAILABILITY = "manage:availability"
    VIEW_CARE_DASHBOARD = "view:care-dashboard"
    
    # Journal Features
    CREATE_JOURNALS = "create:journals"
    VIEW_PATIENT_JOURNALS = "view:patient-journals"
    
    # Admin Features
    ACCESS_ADMIN_PANEL = "access:admin-panel"
    MANAGE_ALL_USERS = "manage:all-users"
    VIEW_SYSTEM_STATS = "view:system-stats"


class RoleScopes:
    """Predefined scope sets for each role."""
    
    USER = [
        Scopes.JOIN_APPOINTMENTS,
        Scopes.CREATE_JOURNALS,
        Scopes.CANCEL_APPOINTMENTS,
    ]
    
    CARE_PROVIDER = USER + [
        Scopes.CREATE_APPOINTMENTS,
        Scopes.UPDATE_APPOINTMENTS,
        Scopes.VIEW_ALL_APPOINTMENTS,
        Scopes.VIEW_ASSIGNED_USERS,
        Scopes.VIEW_USER_PROFILES,
        Scopes.MANAGE_AVAILABILITY,
        Scopes.VIEW_CARE_DASHBOARD,
        Scopes.VIEW_PATIENT_JOURNALS,
    ]
    
    ADMIN = CARE_PROVIDER + [
        Scopes.ACCESS_ADMIN_PANEL,
        Scopes.MANAGE_ALL_USERS,
        Scopes.MANAGE_USER_ASSIGNMENTS,
        Scopes.VIEW_SYSTEM_STATS,
    ]


def has_scope(auth: AuthInfo, required_scope: str) -> bool:
    """
    Check if the authenticated user has a specific scope.
    
    Args:
        auth: Authentication information from JWT token
        required_scope: The scope to check for
        
    Returns:
        True if user has the scope, False otherwise
    """
    return auth.has_scope(required_scope)


def has_any_scope(auth: AuthInfo, required_scopes: List[str]) -> bool:
    """
    Check if the authenticated user has any of the specified scopes.
    
    Args:
        auth: Authentication information from JWT token
        required_scopes: List of scopes to check for
        
    Returns:
        True if user has at least one of the scopes, False otherwise
    """
    return auth.has_any_scope(required_scopes)


def has_all_scopes(auth: AuthInfo, required_scopes: List[str]) -> bool:
    """
    Check if the authenticated user has all of the specified scopes.
    
    Args:
        auth: Authentication information from JWT token
        required_scopes: List of scopes to check for
        
    Returns:
        True if user has all scopes, False otherwise
    """
    return auth.has_all_scopes(required_scopes)


def require_scope(auth: AuthInfo, required_scope: str, error_message: Optional[str] = None) -> None:
    """
    Require a specific scope or raise HTTPException.
    
    Args:
        auth: Authentication information from JWT token
        required_scope: The scope to require
        error_message: Custom error message (optional)
        
    Raises:
        HTTPException: If user doesn't have the required scope
    """
    if not has_scope(auth, required_scope):
        message = error_message or f"Insufficient permissions. Required scope: {required_scope}"
        raise HTTPException(status_code=403, detail=message)


def require_any_scope(auth: AuthInfo, required_scopes: List[str], error_message: Optional[str] = None) -> None:
    """
    Require any of the specified scopes or raise HTTPException.
    
    Args:
        auth: Authentication information from JWT token
        required_scopes: List of scopes, user needs at least one
        error_message: Custom error message (optional)
        
    Raises:
        HTTPException: If user doesn't have any of the required scopes
    """
    if not has_any_scope(auth, required_scopes):
        message = error_message or f"Insufficient permissions. Required any of: {', '.join(required_scopes)}"
        raise HTTPException(status_code=403, detail=message)


def require_all_scopes(auth: AuthInfo, required_scopes: List[str], error_message: Optional[str] = None) -> None:
    """
    Require all of the specified scopes or raise HTTPException.
    
    Args:
        auth: Authentication information from JWT token
        required_scopes: List of scopes, user needs all of them
        error_message: Custom error message (optional)
        
    Raises:
        HTTPException: If user doesn't have all of the required scopes
    """
    if not has_all_scopes(auth, required_scopes):
        missing_scopes = [scope for scope in required_scopes if scope not in auth.scopes]
        message = error_message or f"Insufficient permissions. Missing scopes: {', '.join(missing_scopes)}"
        raise HTTPException(status_code=403, detail=message)


def can_access_user_data(auth: AuthInfo, target_user_id: str) -> bool:
    """
    Check if the authenticated user can access data for a specific user.
    
    Rules:
    - Users can access their own data
    - Care providers can access assigned users' data (if they have the scope)
    - Admins can access all users' data (if they have the scope)
    
    Args:
        auth: Authentication information from JWT token
        target_user_id: ID of the user whose data is being accessed
        
    Returns:
        True if access is allowed, False otherwise
    """
    # Users can always access their own data
    if auth.sub == target_user_id:
        return True
    
    # Care providers can access assigned users if they have the scope
    if has_scope(auth, Scopes.VIEW_ASSIGNED_USERS):
        return True
    
    # Admins can access all users if they have the scope
    if has_scope(auth, Scopes.MANAGE_ALL_USERS):
        return True
    
    return False


def can_manage_appointments_for_user(auth: AuthInfo, target_user_id: str) -> bool:
    """
    Check if the authenticated user can manage appointments for a specific user.
    
    Args:
        auth: Authentication information from JWT token
        target_user_id: ID of the user whose appointments are being managed
        
    Returns:
        True if management is allowed, False otherwise
    """
    # Users can manage their own appointments (if they have create scope)
    if auth.sub == target_user_id and has_scope(auth, Scopes.CREATE_APPOINTMENTS):
        return True
    
    # Care providers can manage appointments for assigned users
    if has_scope(auth, Scopes.CREATE_APPOINTMENTS) and has_scope(auth, Scopes.VIEW_ASSIGNED_USERS):
        return True
    
    # Admins can manage all appointments
    if has_scope(auth, Scopes.CREATE_APPOINTMENTS) and has_scope(auth, Scopes.MANAGE_ALL_USERS):
        return True
    
    return False


def get_user_role_from_scopes(scopes: List[str]) -> str:
    """
    Determine user role based on their scopes.
    
    Args:
        scopes: List of user scopes
        
    Returns:
        Role name as string
    """
    if Scopes.MANAGE_ALL_USERS in scopes:
        return "admin"
    elif Scopes.CREATE_APPOINTMENTS in scopes:
        return "care_provider"
    else:
        return "user"
