"""
Payment model.

WEBHOOK IDEMPOTENCY:
The provider_event_id column has a UNIQUE constraint at the database level.
This is the PRIMARY mechanism for webhook idempotency — not application-level
if-exists checks, which are vulnerable to race conditions.

When two identical webhook events arrive simultaneously:
1. Both read that no payment exists (race window)
2. Both try to INSERT
3. Only ONE succeeds — the other hits the UNIQUE constraint
4. The failing transaction catches the IntegrityError and returns safely

This is why we use database constraints rather than just application logic.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, DateTime, Enum, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False, unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), nullable=False
    )
    # Uniquely identifies an external webhook event — core of idempotency
    provider_event_id: Mapped[str] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(back_populates="payment")  # noqa: F821

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        Index("ix_payments_booking_id", "booking_id"),
        Index("ix_payments_provider_event_id", "provider_event_id"),
    )
