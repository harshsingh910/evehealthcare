"""
CentreTest association model.

WHY THIS TABLE EXISTS:
The same diagnostic test (e.g., CBC) can be offered at different centres
with different prices. This many-to-many relationship with an extra 'price'
attribute requires an association table rather than a simple M2M link.

Example:
  Apollo + CBC = ₹500
  City Lab + CBC = ₹400

The UNIQUE constraint on (centre_id, test_id) prevents duplicate offerings.
The CHECK constraint ensures price is always positive.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, DateTime, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CentreTest(Base):
    __tablename__ = "centre_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diagnostic_centres.id"), nullable=False
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diagnostic_tests.id"), nullable=False
    )
    # Decimal(10,2) handles prices up to 99,999,999.99 — sufficient for diagnostic tests
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    centre: Mapped["DiagnosticCentre"] = relationship(back_populates="centre_tests")  # noqa: F821
    test: Mapped["DiagnosticTest"] = relationship(back_populates="centre_tests")  # noqa: F821

    __table_args__ = (
        # Prevent duplicate centre-test combinations
        UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
        # Database-level price validation — defense in depth beyond Pydantic
        CheckConstraint("price > 0", name="ck_centre_test_price_positive"),
        Index("ix_centre_tests_centre_id", "centre_id"),
        Index("ix_centre_tests_test_id", "test_id"),
    )
