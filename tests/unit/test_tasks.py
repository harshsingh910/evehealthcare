"""
Unit tests for background Celery tasks (app/tasks/).

Tests webhook async processing, retry logic on transient failure,
permanent failure handling (no retry), and notification simulation tasks.
"""

from unittest.mock import MagicMock, patch
from decimal import Decimal
import pytest

from app.tasks.payment_tasks import process_webhook_async
from app.tasks.notification_tasks import send_booking_confirmation, send_payment_receipt
from app.utils.exceptions import NotFoundError, BadRequestError, ConflictError


def test_send_booking_confirmation():
    task = send_booking_confirmation
    result = task.run("bkg-123", "user@example.com")
    assert result["sent"] is True
    assert result["booking_id"] == "bkg-123"
    assert result["email"] == "user@example.com"


def test_send_payment_receipt():
    task = send_payment_receipt
    result = task.run("pay-456", "user@example.com")
    assert result["sent"] is True
    assert result["payment_id"] == "pay-456"
    assert result["email"] == "user@example.com"


@patch("app.tasks.payment_tasks.SessionLocal")
@patch("app.tasks.payment_tasks.PaymentService")
def test_process_webhook_async_success(mock_payment_service_cls, mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_service = MagicMock()
    mock_service.process_webhook.return_value = {"status": "SUCCESS", "payment_id": "p-1"}
    mock_payment_service_cls.return_value = mock_service

    result = process_webhook_async.run(
        event_id="evt-100",
        booking_id="bkg-200",
        status="SUCCESS",
        amount="500.00",
    )

    assert result["status"] == "SUCCESS"
    mock_service.process_webhook.assert_called_once_with(
        event_id="evt-100",
        booking_id="bkg-200",
        status="SUCCESS",
        amount=Decimal("500.00"),
    )
    mock_db.close.assert_called_once()


@patch("app.tasks.payment_tasks.SessionLocal")
@patch("app.tasks.payment_tasks.PaymentService")
def test_process_webhook_async_permanent_failure(mock_payment_service_cls, mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_service = MagicMock()
    mock_service.process_webhook.side_effect = NotFoundError(detail="Booking not found")
    mock_payment_service_cls.return_value = mock_service

    result = process_webhook_async.run(
        event_id="evt-404",
        booking_id="bkg-nonexistent",
        status="SUCCESS",
        amount="500.00",
    )

    assert result["retryable"] is False
    assert "Booking not found" in result["error"]
    mock_db.close.assert_called_once()


@patch("app.tasks.payment_tasks.SessionLocal")
@patch("app.tasks.payment_tasks.PaymentService")
def test_process_webhook_async_transient_failure_retries(mock_payment_service_cls, mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_service = MagicMock()
    mock_service.process_webhook.side_effect = ConnectionError("DB connection lost")
    mock_payment_service_cls.return_value = mock_service

    with patch.object(process_webhook_async, "retry", side_effect=Exception("Retry scheduled")) as mock_retry:
        res = process_webhook_async.apply(
            args=["evt-retry", "bkg-retry", "SUCCESS", "500.00"]
        )

        mock_retry.assert_called_once()
        assert res.status == "FAILURE"
    mock_db.close.assert_called_once()

