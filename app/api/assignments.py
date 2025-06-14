"""API endpoints for user-care provider assignments"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.database import get_db
from app.db.models import User, UserRole, UserAssignment
from app.schemas.assignment import (
    UserAssignment as UserAssignmentSchema,
    UserAssignmentCreate,
    UserAssignmentUpdate,
    UserAssignmentWithDetails,
    BulkUserAssignmentCreate,
    AssignmentStats,
)
from app.api.deps import get_current_user
from app.api.role_deps import require_admin, require_care_or_admin

router = APIRouter()


@router.get("/", response_model=List[UserAssignmentWithDetails])
def get_assignments(
    skip: int = 0,
    limit: int = 100,
    user_id: str = None,
    care_provider_id: str = None,
    is_active: bool = None,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get user assignments with filtering options.
    - Admins: Can see all assignments
    - Care providers: Can only see their own assignments
    """
    query = db.query(UserAssignment)

    # Role-based filtering
    if current_user.role == UserRole.CARE_PROVIDER:
        # Care providers can only see their own assignments
        query = query.filter(UserAssignment.care_provider_id == current_user.id)
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Apply filters
    if user_id:
        query = query.filter(UserAssignment.user_id == user_id)
    if care_provider_id:
        query = query.filter(UserAssignment.care_provider_id == care_provider_id)
    if is_active is not None:
        query = query.filter(UserAssignment.is_active == is_active)

    assignments = query.offset(skip).limit(limit).all()

    # Enrich with user details
    result = []
    for assignment in assignments:
        user = db.query(User).filter(User.id == assignment.user_id).first()
        care_provider = db.query(User).filter(User.id == assignment.care_provider_id).first()
        assigner = db.query(User).filter(User.id == assignment.assigned_by).first() if assignment.assigned_by else None

        assignment_dict = {
            "id": assignment.id,
            "user_id": assignment.user_id,
            "care_provider_id": assignment.care_provider_id,
            "assigned_at": assignment.assigned_at,
            "assigned_by": assignment.assigned_by,
            "is_active": assignment.is_active,
            "notes": assignment.notes,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_first_name": user.first_name if user else None,
            "user_last_name": user.last_name if user else None,
            "user_country": user.country if user else None,
            "care_provider_name": care_provider.name if care_provider else None,
            "care_provider_email": care_provider.email if care_provider else None,
            "care_provider_first_name": care_provider.first_name if care_provider else None,
            "care_provider_last_name": care_provider.last_name if care_provider else None,
            "assigner_name": assigner.name if assigner else None,
        }
        result.append(assignment_dict)

    return result


@router.post("/", response_model=UserAssignmentSchema, status_code=status.HTTP_201_CREATED)
def create_assignment(
    assignment_in: UserAssignmentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new user assignment. Admin only.
    """
    # Validate user exists and is a regular user
    user = db.query(User).filter(
        User.id == assignment_in.user_id,
        User.role == UserRole.USER,
        User.is_active == True
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not a regular user"
        )

    # Validate care provider exists and is a care provider
    care_provider = db.query(User).filter(
        User.id == assignment_in.care_provider_id,
        User.role == UserRole.CARE_PROVIDER,
        User.is_active == True
    ).first()
    if not care_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider not found or not a care provider"
        )

    # Check if assignment already exists
    existing_assignment = db.query(UserAssignment).filter(
        UserAssignment.user_id == assignment_in.user_id,
        UserAssignment.care_provider_id == assignment_in.care_provider_id
    ).first()

    if existing_assignment:
        if existing_assignment.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active assignment already exists between this user and care provider"
            )
        else:
            # Reactivate existing assignment
            existing_assignment.is_active = True
            existing_assignment.assigned_by = current_user.id
            existing_assignment.notes = assignment_in.notes
            db.commit()
            db.refresh(existing_assignment)
            return existing_assignment

    # Create new assignment
    assignment = UserAssignment(
        user_id=assignment_in.user_id,
        care_provider_id=assignment_in.care_provider_id,
        assigned_by=current_user.id,
        notes=assignment_in.notes,
        is_active=True
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment


@router.post("/bulk", response_model=List[UserAssignmentSchema], status_code=status.HTTP_201_CREATED)
def create_bulk_assignments(
    bulk_assignment_in: BulkUserAssignmentCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create multiple user assignments at once. Admin only.
    """
    # Validate care provider exists and is a care provider
    care_provider = db.query(User).filter(
        User.id == bulk_assignment_in.care_provider_id,
        User.role == UserRole.CARE_PROVIDER,
        User.is_active == True
    ).first()
    if not care_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Care provider not found or not a care provider"
        )

    # Validate all users exist and are regular users
    users = db.query(User).filter(
        User.id.in_(bulk_assignment_in.user_ids),
        User.role == UserRole.USER,
        User.is_active == True
    ).all()

    if len(users) != len(bulk_assignment_in.user_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some users not found or not regular users"
        )

    created_assignments = []
    errors = []

    for user_id in bulk_assignment_in.user_ids:
        try:
            # Check if assignment already exists
            existing_assignment = db.query(UserAssignment).filter(
                UserAssignment.user_id == user_id,
                UserAssignment.care_provider_id == bulk_assignment_in.care_provider_id
            ).first()

            if existing_assignment:
                if existing_assignment.is_active:
                    errors.append(f"User {user_id}: Active assignment already exists")
                    continue
                else:
                    # Reactivate existing assignment
                    existing_assignment.is_active = True
                    existing_assignment.assigned_by = current_user.id
                    existing_assignment.notes = bulk_assignment_in.notes
                    created_assignments.append(existing_assignment)
            else:
                # Create new assignment
                assignment = UserAssignment(
                    user_id=user_id,
                    care_provider_id=bulk_assignment_in.care_provider_id,
                    assigned_by=current_user.id,
                    notes=bulk_assignment_in.notes,
                    is_active=True
                )
                db.add(assignment)
                created_assignments.append(assignment)
        except Exception as e:
            errors.append(f"User {user_id}: {str(e)}")

    if errors:
        # If there are errors, still commit successful assignments but return error info
        db.commit()
        for assignment in created_assignments:
            db.refresh(assignment)

        raise HTTPException(
            status_code=status.HTTP_207_MULTI_STATUS,
            detail={
                "message": "Some assignments failed",
                "errors": errors,
                "successful_assignments": len(created_assignments)
            }
        )

    db.commit()
    for assignment in created_assignments:
        db.refresh(assignment)

    return created_assignments


@router.get("/{assignment_id}", response_model=UserAssignmentWithDetails)
def get_assignment(
    assignment_id: str,
    current_user: User = Depends(require_care_or_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific assignment by ID.
    """
    assignment = db.query(UserAssignment).filter(UserAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    # Check permissions
    if current_user.role == UserRole.CARE_PROVIDER:
        if assignment.care_provider_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Enrich with user details
    user = db.query(User).filter(User.id == assignment.user_id).first()
    care_provider = db.query(User).filter(User.id == assignment.care_provider_id).first()
    assigner = db.query(User).filter(User.id == assignment.assigned_by).first() if assignment.assigned_by else None

    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "care_provider_id": assignment.care_provider_id,
        "assigned_at": assignment.assigned_at,
        "assigned_by": assignment.assigned_by,
        "is_active": assignment.is_active,
        "notes": assignment.notes,
        "user_name": user.name if user else None,
        "user_email": user.email if user else None,
        "user_first_name": user.first_name if user else None,
        "user_last_name": user.last_name if user else None,
        "user_country": user.country if user else None,
        "care_provider_name": care_provider.name if care_provider else None,
        "care_provider_email": care_provider.email if care_provider else None,
        "care_provider_first_name": care_provider.first_name if care_provider else None,
        "care_provider_last_name": care_provider.last_name if care_provider else None,
        "assigner_name": assigner.name if assigner else None,
    }


@router.put("/{assignment_id}", response_model=UserAssignmentSchema)
def update_assignment(
    assignment_id: str,
    assignment_in: UserAssignmentUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update an assignment. Admin only.
    """
    assignment = db.query(UserAssignment).filter(UserAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    # Update fields
    if assignment_in.is_active is not None:
        assignment.is_active = assignment_in.is_active
    if assignment_in.notes is not None:
        assignment.notes = assignment_in.notes

    db.commit()
    db.refresh(assignment)

    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """
    Deactivate an assignment (soft delete). Admin only.
    """
    assignment = db.query(UserAssignment).filter(UserAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found"
        )

    assignment.is_active = False
    db.commit()


@router.get("/stats/overview", response_model=AssignmentStats)
def get_assignment_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get assignment statistics. Admin only.
    """
    total_assignments = db.query(UserAssignment).count()
    active_assignments = db.query(UserAssignment).filter(UserAssignment.is_active == True).count()
    inactive_assignments = total_assignments - active_assignments

    users_assigned = db.query(UserAssignment.user_id).filter(UserAssignment.is_active == True).distinct().count()
    care_providers_with_assignments = db.query(UserAssignment.care_provider_id).filter(UserAssignment.is_active == True).distinct().count()

    return {
        "total_assignments": total_assignments,
        "active_assignments": active_assignments,
        "inactive_assignments": inactive_assignments,
        "users_assigned": users_assigned,
        "care_providers_with_assignments": care_providers_with_assignments,
    }
