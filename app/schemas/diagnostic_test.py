"""Diagnostic test schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from pydantic import BaseModel


class CentreForTest(BaseModel):
    """A centre that offers this test, with price."""
    centre_id: uuid.UUID
    centre_name: str
    price: Decimal

    model_config = {"from_attributes": True}


class DiagnosticTestResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiagnosticTestDetailResponse(BaseModel):
    """Test detail with centres that offer it."""
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    centres: list[CentreForTest] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestListResponse(BaseModel):
    __test__ = False
    items: Sequence[DiagnosticTestResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
