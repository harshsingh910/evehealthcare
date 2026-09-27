"""
Database engine and session configuration.

Uses SQLAlchemy 2.x with synchronous sessions (simpler for interview discussion).
Alembic handles all schema migrations — create_all() is NOT used in production.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# Synchronous engine — straightforward for this scale.
# Connection pool defaults (pool_size=5, max_overflow=10) are sensible for a monolith.
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Detect stale connections before use
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass
