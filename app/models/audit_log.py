"""
Audit Log model.

Records important business and security events in PostgreSQL.
Used for compliance, debugging, and security analysis.

DESIGN:
- Separate from operational stdout logs (structured JSON to Railway).
- Only stores significant business/security events, not every request.
- JSONB metadata field for flexible, event-specific context.
- actor_user_id is nullable — some events (e.g., LOGIN_FAILURE) occur
  before or without a known authenticated user.
- Never stores passwords, JWT tokens, or other sensitive credentials.

INDEXED FIELDS:
- actor_user_id: query all events by user
- event_type: filter by event category
- created_at: time-range queries and retention cleanup
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Index, Enum, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditEventType(str, enum.Enum):
    # Authentication events
    USER_SIGNUP = "USER_SIGNUP"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_REVOKED = "SESSION_REVOKED"

    # Booking events
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"

    # Payment events
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    WEBHOOK_PROCESSED = "WEBHOOK_PROCESSED"
    WEBHOOK_DUPLICATE = "WEBHOOK_DUPLICATE"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # actor_user_id nullable — LOGIN_FAILURE may not have an authenticated user
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="audit_event_type"),
        nullable=False,
    )
    # Entity affected by the event (e.g., "booking", "payment")
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Request correlation (from X-Request-ID header)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Flexible metadata — event-specific details (JSONB for PostgreSQL, JSON for SQLite)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
