"""
Booking model with explicit state machine.

BOOKING STATE MACHINE:
  PENDING → CONFIRMED  (on successful payment)
  PENDING → FAILED     (on failed payment)
  PENDING → CANCELLED  (user cancellation)
  CONFIRMED → CANCELLED (user cancellation after payment)

Invalid transitions (e.g., FAILED → CONFIRMED) are rejected
at the service layer. This prevents state corruption from
race conditions or invalid webhook events.

The amount is COPIED from CentreTest.price at booking time,
never accepted from the client. This is a snapshot — if the
centre later changes the test price, existing bookings are unaffected.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, DateTime, Enum, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Explicit allowed transitions — makes the state machine auditable
ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
    BookingStatus.FAILED: set(),
    BookingStatus.CANCELLED: set(),
}


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diagnostic_centres.id"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diagnostic_tests.id"), nullable=False
    )
    appointment_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"),
        nullable=False,
        default=BookingStatus.PENDING,
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
    user: Mapped["User"] = relationship(back_populates="bookings")  # noqa: F821
    centre: Mapped["DiagnosticCentre"] = relationship(back_populates="bookings")  # noqa: F821
    test: Mapped["DiagnosticTest"] = relationship(back_populates="bookings")  # noqa: F821
    payment: Mapped["Payment"] = relationship(  # noqa: F821
        back_populates="booking", uselist=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_booking_amount_positive"),
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_centre_id", "centre_id"),
        Index("ix_bookings_test_id", "test_id"),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_appointment_datetime", "appointment_datetime"),
    )
