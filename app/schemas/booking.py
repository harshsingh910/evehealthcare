"""Booking schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from pydantic import BaseModel, Field, field_validator


class BookingCreateRequest(BaseModel):
    """
    Booking creation request.

    IMPORTANT: No 'amount' field — the price is derived server-side
    from the centre_tests table. This prevents price manipulation attacks.
    """
    centre_id: uuid.UUID
    test_id: uuid.UUID
    appointment_datetime: datetime = Field(
        ..., description="Appointment date/time in ISO 8601 format (must be in the future)"
    )


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    appointment_datetime: datetime
    amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
    centre_name: Optional[str] = None
    test_name: Optional[str] = None

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    items: Sequence[BookingResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
