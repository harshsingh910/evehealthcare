"""
Pagination utility for list endpoints.

Uses SQL-level OFFSET/LIMIT for efficiency — never loads entire tables into memory.
Maximum page_size is capped to prevent abuse.
"""

from typing import TypeVar, Generic, Sequence
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""
    items: Sequence[T]
    page: int
    page_size: int
    total: int
    total_pages: int


def paginate(db: Session, query: Select, page: int, page_size: int) -> tuple[list, int]:
    """
    Apply pagination to a SQLAlchemy query.

    Returns (items, total_count).
    Uses SQL COUNT and OFFSET/LIMIT for database-level pagination.
    """
    # Count total matching rows
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Apply offset/limit
    offset = (page - 1) * page_size
    items = db.execute(query.offset(offset).limit(page_size)).scalars().all()

    return list(items), total


def build_paginated_response(
    items: list, page: int, page_size: int, total: int
) -> dict:
    """Build the paginated response dict."""
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
