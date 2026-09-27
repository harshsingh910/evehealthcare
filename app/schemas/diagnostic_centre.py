"""Diagnostic centre schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from pydantic import BaseModel


class CentreTestItem(BaseModel):
    """A test offered by a centre, with centre-specific pricing."""
    id: uuid.UUID
    name: str
    price: Decimal

    model_config = {"from_attributes": True}


class DiagnosticCentreResponse(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiagnosticCentreDetailResponse(BaseModel):
    """Centre detail with its available tests and prices."""
    id: uuid.UUID
    name: str
    location: str
    tests: list[CentreTestItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CentreListResponse(BaseModel):
    items: Sequence[DiagnosticCentreResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
