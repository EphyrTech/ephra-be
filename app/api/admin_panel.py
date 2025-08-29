"""Admin panel routes with Jinja2 templates and comprehensive logging"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import (APIRouter, Depends, Form, HTTPException, Request,
                     Response, status)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.core.admin_auth import (AdminSession, admin_sessions,
                                 authenticate_superadmin, create_admin_session,
                                 get_admin_session, get_client_ip,
                                 get_user_agent, invalidate_admin_session,
                                 log_admin_action, require_admin_session)
from app.core.config import settings
from app.db.database import get_db
from app.db.models import (Appointment, AppointmentStatus, Availability,
                           CareProviderProfile, Journal, MediaFile,
                           PersonalJournal, SpecialistType, User, UserRole)

logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Router with uncommon path for security
router = APIRouter(prefix="/admin-control-panel-x7k9m2", tags=["Admin Panel"])

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: Optional[str] = None):
    """Display admin login page"""
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "error": error
    })

@router.post("/login")
async def admin_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle admin login"""
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Log login attempt
    logger.info(f"Admin login attempt - Username: {username}, IP: {ip_address}")
    
    if not authenticate_superadmin(username, password):
        logger.warning(f"Failed admin login attempt - Username: {username}, IP: {ip_address}")
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=401)
    
    # Create session
    session_id = create_admin_session(username, ip_address, user_agent)
    
    # Set secure cookie
    response = RedirectResponse(url="/admin-control-panel-x7k9m2/dashboard", status_code=302)
    response.set_cookie(
        key="admin_session_id",
        value=session_id,
        max_age=8 * 60 * 60,  # 8 hours
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict"
    )
    
    logger.info(f"Successful admin login - Username: {username}, IP: {ip_address}, Session: {session_id}")
    return response

@router.get("/logout")
async def admin_logout(
    request: Request,
    response: Response,
    session: AdminSession = Depends(require_admin_session)
):
    """Handle admin logout"""
    session_id = request.cookies.get("admin_session_id")
    if session_id:
        invalidate_admin_session(session_id)
    
    response = RedirectResponse(url="/admin-control-panel-x7k9m2/login", status_code=302)
    response.delete_cookie("admin_session_id")
    
    log_admin_action(session, "LOGOUT")
    return response

@router.get("/session-info")
async def session_info(session: AdminSession = Depends(require_admin_session)):
    """Get current session info for AJAX checks"""
    return {"valid": True, "session": session.to_dict()}

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Admin dashboard with statistics and overview"""
    log_admin_action(session, "VIEW_DASHBOARD")
    
    # Get statistics
    stats = {
        "total_users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "total_journals": db.query(Journal).count(),
        "total_appointments": db.query(Appointment).count(),
    }
    
    # Get recent activity (last 10 users)
    recent_activity = db.query(User).order_by(desc(User.created_at)).limit(10).all()
    activity_list = []
    for user in recent_activity:
        activity_list.append({
            "user_name": user.name or user.display_name,
            "user_email": user.email,
            "action": "User Registration",
            "created_at": user.created_at,
            "status": "active" if user.is_active else "inactive"
        })
    
    # System information
    system_info = {
        "environment": settings.ENVIRONMENT,
        "database_status": "Connected",
        "active_admin_sessions": len(admin_sessions),
        "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime": "N/A"  # Could be calculated if needed
    }
    
    # Chart data (last 7 days)
    chart_data = get_dashboard_chart_data(db)
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "session": session,
        "stats": stats,
        "recent_activity": activity_list,
        "system_info": system_info,
        "chart_data": chart_data
    })

def get_dashboard_chart_data(db: Session) -> Dict[str, Any]:
    """Get chart data for dashboard"""
    # User registration trend (last 7 days)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=6)
    
    user_registration_data = []
    user_registration_labels = []
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        count = db.query(User).filter(
            func.date(User.created_at) == date
        ).count()
        user_registration_data.append(count)
        user_registration_labels.append(date.strftime("%m/%d"))
    
    # Journal entries (last 7 days)
    journal_entries_data = []
    journal_entries_labels = []
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        count = db.query(Journal).filter(
            func.date(Journal.created_at) == date
        ).count()
        journal_entries_data.append(count)
        journal_entries_labels.append(date.strftime("%m/%d"))
    
    return {
        "user_registration_labels": user_registration_labels,
        "user_registration_data": user_registration_data,
        "journal_entries_labels": journal_entries_labels,
        "journal_entries_data": journal_entries_data
    }

@router.get("/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None
):
    """List all users with pagination and search"""
    log_admin_action(session, "VIEW_USERS", {"page": page, "search": search})
    
    query = db.query(User)
    
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) |
            (User.name.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )
    
    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("admin/users_list.html", {
        "request": request,
        "session": session,
        "users": users,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "search": search or ""
    })

@router.get("/sessions", response_class=HTMLResponse)
async def admin_sessions_list(
    request: Request,
    session: AdminSession = Depends(require_admin_session)
):
    """List active admin sessions"""
    log_admin_action(session, "VIEW_SESSIONS")
    
    return templates.TemplateResponse("admin/sessions.html", {
        "request": request,
        "session": session,
        "sessions": list(admin_sessions.values())
    })

@router.get("/audit-log", response_class=HTMLResponse)
async def admin_audit_log(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    page: int = 1,
    per_page: int = 50
):
    """Display audit log of admin actions"""
    log_admin_action(session, "VIEW_AUDIT_LOG", {"page": page})
    
    # In a real implementation, you would read from a log file or database
    # For now, we'll show a placeholder
    audit_entries = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "admin_user": session.username,
            "ip_address": session.ip_address,
            "action": "VIEW_AUDIT_LOG",
            "details": {"page": page}
        }
    ]
    
    return templates.TemplateResponse("admin/audit_log.html", {
        "request": request,
        "session": session,
        "audit_entries": audit_entries,
        "page": page,
        "per_page": per_page
    })

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """View user details"""
    log_admin_action(session, "VIEW_USER_DETAIL", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's journals
    journals = db.query(Journal).filter(Journal.user_id == user_id).order_by(desc(Journal.created_at)).limit(10).all()

    # Get user's appointments
    appointments = db.query(Appointment).filter(Appointment.user_id == user_id).order_by(desc(Appointment.created_at)).limit(10).all()

    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request,
        "session": session,
        "user": user,
        "journals": journals,
        "appointments": appointments
    })

@router.post("/users/{user_id}/activate")
async def admin_activate_user(
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Activate user"""
    log_admin_action(session, "ACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = True
    db.commit()

    return {"success": True, "message": "User activated successfully"}

@router.post("/users/{user_id}/deactivate")
async def admin_deactivate_user(
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Deactivate user"""
    log_admin_action(session, "DEACTIVATE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_active = False
    db.commit()

    return {"success": True, "message": "User deactivated successfully"}

@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: str,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db)
):
    """Delete user (soft delete by deactivating)"""
    log_admin_action(session, "DELETE_USER", {"user_id": user_id})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found"}

    # Soft delete by deactivating
    user.is_active = False
    db.commit()

    return {"success": True, "message": "User deleted successfully"}

@router.get("/journals", response_class=HTMLResponse)
async def admin_journals_list(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all journals"""
    log_admin_action(session, "VIEW_JOURNALS", {"page": page})

    query = db.query(Journal).options(joinedload(Journal.user)).order_by(desc(Journal.created_at))
    total = query.count()
    journals = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/journals_list.html", {
        "request": request,
        "session": session,
        "journals": journals,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })

@router.get("/appointments", response_class=HTMLResponse)
async def admin_appointments_list(
    request: Request,
    session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 20
):
    """List all appointments"""
    log_admin_action(session, "VIEW_APPOINTMENTS", {"page": page})

    query = db.query(Appointment).options(
        joinedload(Appointment.user),
        joinedload(Appointment.care_provider)
    ).order_by(desc(Appointment.created_at))

    total = query.count()
    appointments = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse("admin/appointments_list.html", {
        "request": request,
        "session": session,
        "appointments": appointments,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages
    })
