"""Payment schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    """
    Simulated payment request.

    simulate_status allows deterministic testing — in production,
    this would be replaced by actual gateway integration.
    Amount is NOT accepted from client; it's derived from the booking.
    """
    booking_id: uuid.UUID
    simulate_status: str = Field(
        ...,
        pattern="^(SUCCESS|FAILED)$",
        description="Simulated outcome: SUCCESS or FAILED",
    )


class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    status: str
    provider_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookRequest(BaseModel):
    """
    External payment provider webhook payload.

    event_id is the provider's unique event identifier —
    used with a UNIQUE DB constraint for idempotent processing.
    """
    event_id: str = Field(..., min_length=1, description="Provider's unique event ID")
    booking_id: uuid.UUID
    status: str = Field(
        ...,
        pattern="^(SUCCESS|FAILED)$",
        description="Payment outcome: SUCCESS or FAILED",
    )
    amount: Decimal = Field(..., gt=0, description="Payment amount (must match booking)")


class WebhookResponse(BaseModel):
    message: str
    payment_id: Optional[uuid.UUID] = None
    status: str
