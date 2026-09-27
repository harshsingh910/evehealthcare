"""
Audit logging service.

Provides a single write point for all audit events.

DESIGN PRINCIPLES:
1. FIRE-AND-FORGET SAFETY: audit_service.log() must never cause a
   successful business operation to fail. All write errors are caught
   and logged to stdout only.

2. NO SENSITIVE DATA: Callers must never pass tokens, passwords,
   hashed passwords, JWTs, or database credentials as metadata.

3. SHARED SESSION: Uses the request's DB session so that audit records
   and business records can be committed together when transactionally
   appropriate. When called after a business commit (e.g. from a router),
   the audit record is committed in its own immediate commit.

4. SQLALCHEMY COMPATIBILITY: metadata_ is stored as JSONB on PostgreSQL
   and Text on SQLite (for tests). JSON serialisation is applied manually
   for SQLite compatibility.
"""

import json
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, AuditEventType
from app.core.logging import get_logger

logger = get_logger(__name__)


def _safe_json(value: Any) -> Any:
    """
    Ensure metadata is JSON-serialisable, converting UUIDs/Decimals to str.
    Returns None if serialisation fails — audit must not break business logic.
    """
    if value is None:
        return None
    try:
        # Round-trip through JSON to normalise types
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"error": "metadata serialisation failed"}


class AuditService:
    """
    Service for writing business/security audit records to the database.

    Typical usage:
        audit = AuditService(db)
        audit.log(
            event_type=AuditEventType.BOOKING_CREATED,
            actor_user_id=current_user.id,
            entity_type="booking",
            entity_id=str(booking.id),
            metadata={"centre_id": str(centre_id), "amount": str(amount)},
        )
    """

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        event_type: AuditEventType,
        actor_user_id: Optional[uuid.UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Write an audit record.

        This method intentionally swallows all exceptions — an audit
        write failure must never cause a business operation to fail.
        The error is still logged to stdout for observability.

        NEVER pass passwords, tokens, JWTs, or secrets in `metadata`.
        """
        try:
            record = AuditLog(
                event_type=event_type,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                request_id=request_id,
                metadata_=_safe_json(metadata),
            )
            self.db.add(record)
            self.db.flush()  # Don't commit — let the caller control transaction
            logger.debug(
                "Audit event recorded",
                extra={
                    "audit_event": event_type.value,
                    "actor_user_id": str(actor_user_id) if actor_user_id else None,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
            )
        except Exception as exc:
            # Audit failure must not propagate to the caller
            logger.error(
                f"Failed to write audit log: {exc}",
                extra={"audit_event": event_type.value},
            )
