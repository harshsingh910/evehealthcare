"""Unit tests for AuditService and audit logging."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from app.models.audit_log import AuditLog, AuditEventType
from app.services.audit_service import AuditService, _safe_json


def test_safe_json_serialization():
    """Verify _safe_json handles UUID, Decimal, and nested structures."""
    uid = uuid.uuid4()
    dec = Decimal("450.50")
    data = {
        "id": uid,
        "amount": dec,
        "tags": ["alpha", "beta"],
        "nested": {"active": True},
    }
    result = _safe_json(data)
    assert result["id"] == str(uid)
    assert result["amount"] == "450.50"
    assert result["tags"] == ["alpha", "beta"]
    assert result["nested"]["active"] is True


def test_safe_json_none():
    """Verify _safe_json returns None for None input."""
    assert _safe_json(None) is None


def test_audit_service_log_success():
    """Verify AuditService logs event and calls db.add and db.flush."""
    mock_db = MagicMock()
    service = AuditService(mock_db)

    actor_id = uuid.uuid4()
    service.log(
        event_type=AuditEventType.BOOKING_CREATED,
        actor_user_id=actor_id,
        entity_type="booking",
        entity_id="12345",
        metadata={"amount": Decimal("500.00")},
    )

    assert mock_db.add.called
    added_record = mock_db.add.call_args[0][0]
    assert isinstance(added_record, AuditLog)
    assert added_record.event_type == AuditEventType.BOOKING_CREATED
    assert added_record.actor_user_id == actor_id
    assert added_record.entity_type == "booking"
    assert added_record.metadata_ == {"amount": "500.00"}
    assert mock_db.flush.called


def test_audit_service_swallows_db_errors():
    """Verify AuditService never raises even if DB flush fails (fire-and-forget safety)."""
    mock_db = MagicMock()
    mock_db.flush.side_effect = RuntimeError("DB connection lost")
    service = AuditService(mock_db)

    # Should not raise exception
    service.log(
        event_type=AuditEventType.LOGIN_FAILURE,
        actor_user_id=None,
        metadata={"email": "attacker@example.com"},
    )
    assert mock_db.add.called
