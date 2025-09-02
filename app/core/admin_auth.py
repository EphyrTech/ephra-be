"""Admin panel authentication and session management"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.security import verify_password
from app.db.database import get_db
from app.db.models import User, UserRole

logger = logging.getLogger(__name__)

# In-memory session store (in production, use Redis or database)
admin_sessions = {}

# In-memory audit log store (in production, use database or log aggregation)
audit_log_entries = []

class AdminSession:
    def __init__(self, session_id: str, username: str, ip_address: str, user_agent: str, user_id: str):
        self.session_id = session_id
        self.username = username
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = datetime.now(tz=timezone.utc)
        self.last_activity = datetime.now(tz=timezone.utc)
        self.user_id = user_id
        self.expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=8)  # 8 hour session

    def is_valid(self) -> bool:
        return datetime.now(tz=timezone.utc) < self.expires_at

    def update_activity(self):
        self.last_activity = datetime.now(tz=timezone.utc)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for forwarded headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    if hasattr(request.client, 'host'):
        return request.client.host
    
    return "unknown"

def get_user_agent(request: Request) -> str:
    """Get user agent from request"""
    return request.headers.get("User-Agent", "unknown")

def authenticate_superadmin(username: str, password: str, db: Optional[Session] = None) -> bool:
    """Authenticate superadmin credentials - checks both hardcoded superadmin and database admin users"""
    # First check hardcoded superadmin credentials
    if (username == settings.SUPERADMIN_USERNAME and
        password == settings.SUPERADMIN_PASSWORD):
        return True

    # If database session is provided, check for admin users in database
    if db is not None:
        # Check if username is an email (admin users in DB)
        if "@" in username:
            admin_user = db.query(User).filter(
                User.email == username,
                User.role == UserRole.ADMIN,
                User.is_active == True
            ).first()

            if admin_user and admin_user.hashed_password:
                return verify_password(password, admin_user.hashed_password)

    return False

def create_admin_session(username: str, ip_address: str, user_agent: str, user_id: str) -> str:
    """Create a new admin session"""
    session_id = secrets.token_urlsafe(32)
    session = AdminSession(session_id, username, ip_address, user_agent, user_id)
    admin_sessions[session_id] = session
    
    # Log session creation
    logger.info(f"Admin session created - User: {username}, IP: {ip_address}, Session: {session_id}")
    
    return session_id

def get_admin_session(session_id: str) -> Optional[AdminSession]:
    """Get admin session by ID"""
    if not session_id:
        return None
    
    session = admin_sessions.get(session_id)
    if not session:
        return None
    
    if not session.is_valid():
        # Clean up expired session
        del admin_sessions[session_id]
        return None
    
    session.update_activity()
    return session

def invalidate_admin_session(session_id: str) -> bool:
    """Invalidate admin session"""
    if session_id in admin_sessions:
        session = admin_sessions[session_id]
        logger.info(f"Admin session invalidated - User: {session.username}, IP: {session.ip_address}, Session: {session_id}")
        del admin_sessions[session_id]
        return True
    return False

def cleanup_expired_sessions():
    """Clean up expired sessions"""
    expired_sessions = []
    for session_id, session in admin_sessions.items():
        if not session.is_valid():
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del admin_sessions[session_id]

class AdminAuthException(Exception):
    """Custom exception for admin authentication that triggers redirect"""
    pass

def require_admin_session(request: Request, db: Session = Depends(get_db)) -> AdminSession:
    """Dependency to require valid admin session"""
    # Clean up expired sessions periodically
    cleanup_expired_sessions()

    # Get session ID from cookie
    session_id = request.cookies.get("admin_session_id")
    if not session_id:
        # Check if this is an HTML request (browser) vs API request
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Trigger redirect for HTML requests
            raise AdminAuthException("No session")
        else:
            # Return JSON error for API requests
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin authentication required"
            )

    session = get_admin_session(session_id)
    if not session:
        # Check if this is an HTML request (browser) vs API request
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Trigger redirect for HTML requests
            raise AdminAuthException("Invalid session")
        else:
            # Return JSON error for API requests
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired admin session"
            )

    return session

def log_admin_action(session: AdminSession, action: str, details: dict = None):
    """Log admin actions for audit trail"""
    log_data = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "admin_user": session.username,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "action": action,
        "session_id": session.session_id
    }

    if details:
        log_data["details"] = details

    # Add to in-memory audit log
    audit_log_entries.append(log_data)

    # Keep only last 1000 entries to prevent memory issues
    if len(audit_log_entries) > 1000:
        audit_log_entries.pop(0)

    # Log to both application logger and a separate admin audit log
    logger.info(f"ADMIN_ACTION: {log_data}")

    # You could also write to a separate audit log file or database table
    # audit_logger = logging.getLogger("admin_audit")
    # audit_logger.info(log_data)

def get_audit_log_entries(page: int = 1, per_page: int = 50):
    """Get paginated audit log entries"""
    # Return entries in reverse chronological order (newest first)
    reversed_entries = list(reversed(audit_log_entries))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    return reversed_entries[start_idx:end_idx]

def get_recent_audit_entries(limit: int = 10):
    """Get most recent audit entries for live monitoring"""
    return list(reversed(audit_log_entries[-limit:]))

def verify_admin_users_exist(db: Session) -> dict:
    """Verify that admin users exist in the database"""
    try:
        # Count admin users in database
        admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active == True
        ).count()

        # Get list of admin users
        admin_users = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active == True
        ).all()

        admin_list = []
        for admin in admin_users:
            admin_list.append({
                "id": admin.id,
                "email": admin.email,
                "name": admin.name,
                "created_at": admin.created_at.isoformat() if admin.created_at is not None else None,
                "has_password": bool(admin.hashed_password)
            })

        return {
            "success": True,
            "admin_count": admin_count,
            "admins": admin_list,
            "superadmin_configured": bool(settings.SUPERADMIN_USERNAME and settings.SUPERADMIN_PASSWORD)
        }
    except Exception as e:
        logger.error(f"Error verifying admin users: {e}")
        return {
            "success": False,
            "error": str(e),
            "admin_count": 0,
            "admins": []
        }
