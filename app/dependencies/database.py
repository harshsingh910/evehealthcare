"""Database session dependency for FastAPI."""

from typing import Generator
from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session per request.

    The session is committed on success, rolled back on exception,
    and always closed — preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
