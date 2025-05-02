from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.database import get_db

router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        dict: Status information about the API
    """
    return {
        "status": "ok",
        "service": "Mental Health API",
        "version": "1.0.0"
    }

@router.get("/health/db", status_code=status.HTTP_200_OK)
async def db_health_check(db: Session = Depends(get_db)):
    """
    Database health check endpoint.
    
    Executes a simple query to verify database connectivity.
    
    Returns:
        dict: Status information about the database connection
    """
    try:
        # Execute a simple query
        db.execute("SELECT 1")
        return {
            "status": "ok",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }
