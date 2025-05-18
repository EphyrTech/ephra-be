from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Journal, User
from app.schemas.journal import Journal as JournalSchema, JournalCreate, JournalUpdate
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/", response_model=List[JournalSchema])
def get_journals(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Retrieve journals.
    """
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new journal.
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific journal by id.
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
    return journal


@router.put("/{journal_id}", response_model=JournalSchema)
def update_journal(
    journal_id: str,
    journal_in: JournalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a journal.
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a journal.
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
