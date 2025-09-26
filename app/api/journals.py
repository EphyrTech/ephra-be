from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_from_auth
from app.api.rbac_deps import require_create_journals, require_journal_access
from app.core.auth_middleware import AuthInfo, verify_access_token
from app.core.rbac import Scopes, has_scope
from app.db.database import get_db
from app.db.models import Journal, User
from app.schemas.journal import Journal as JournalSchema
from app.schemas.journal import JournalCreate, JournalUpdate

router = APIRouter()


@router.get("/", response_model=List[JournalSchema])
def get_journals(
    skip: int = 0,
    limit: int = 100,
    auth: AuthInfo = Depends(require_journal_access),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve journals. Requires 'create:journals' or 'view:patient-journals' scope.
    - Users with 'create:journals': their own journals
    - Care providers with 'view:patient-journals': all journals
    """
    # If user has patient journal viewing scope, return all journals
    if has_scope(auth, Scopes.VIEW_PATIENT_JOURNALS):
        journals = (
            db.query(Journal)
            .offset(skip)
            .limit(limit)
            .all()
        )
    else:
        # Otherwise, return only user's own journals
        journals = (
            db.query(Journal)
            .filter(Journal.user_id == current_user.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    return journals


@router.post("/", response_model=JournalSchema, status_code=status.HTTP_201_CREATED)
def create_journal(
    journal_in: JournalCreate,
    auth: AuthInfo = Depends(require_create_journals),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new journal. Requires 'create:journals' scope.
    """
    journal = Journal(
        **journal_in.model_dump(),
        user_id=current_user.id,
    )
    db.add(journal)
    db.commit()
    db.refresh(journal)
    return journal


@router.get("/{journal_id}", response_model=JournalSchema)
def get_journal(
    journal_id: str,
    auth: AuthInfo = Depends(require_journal_access),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific journal by id. Requires 'create:journals' or 'view:patient-journals' scope.
    """
    # If user has patient journal viewing scope, can access any journal
    if has_scope(auth, Scopes.VIEW_PATIENT_JOURNALS):
        journal = db.query(Journal).filter(Journal.id == journal_id).first()
    else:
        # Otherwise, can only access own journals
        journal = (
            db.query(Journal)
            .filter(Journal.id == journal_id, Journal.user_id == current_user.id)
            .first()
        )

    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal not found",
        )
    return journal


@router.put("/{journal_id}", response_model=JournalSchema)
def update_journal(
    journal_id: str,
    journal_in: JournalUpdate,
    auth: AuthInfo = Depends(require_create_journals),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a journal. Requires 'create:journals' scope.
    Users can only update their own journals.
    """
    journal = (
        db.query(Journal)
        .filter(Journal.id == journal_id, Journal.user_id == current_user.id)
        .first()
    )
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal not found",
        )

    update_data = journal_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(journal, field, value)

    db.add(journal)
    db.commit()
    db.refresh(journal)
    return journal


@router.delete("/{journal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal(
    journal_id: str,
    auth: AuthInfo = Depends(require_create_journals),
    current_user: User = Depends(get_current_user_from_auth),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a journal. Requires 'create:journals' scope.
    Users can only delete their own journals.
    """
    journal = (
        db.query(Journal)
        .filter(Journal.id == journal_id, Journal.user_id == current_user.id)
        .first()
    )
    if not journal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal not found",
        )

    db.delete(journal)
    db.commit()
