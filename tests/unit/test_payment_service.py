"""Unit tests for PaymentService."""

import uuid
from decimal import Decimal

import pytest

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.services.payment_service import PaymentService
from app.utils.exceptions import NotFoundError, BadRequestError, ForbiddenError, ConflictError


class TestPaymentProcessing:
    def test_payment_success(self, db_session, sample_booking, sample_user):
        service = PaymentService(db_session)
        payment = service.process_payment(
            booking_id=sample_booking.id,
            user_id=sample_user.id,
            simulate_status="SUCCESS",
        )
        assert payment.status == PaymentStatus.SUCCESS
        assert payment.amount == sample_booking.amount
        # Booking should be CONFIRMED
        db_session.refresh(sample_booking)
        assert sample_booking.status == BookingStatus.CONFIRMED

    def test_payment_failure(self, db_session, sample_booking, sample_user):
        service = PaymentService(db_session)
        payment = service.process_payment(
            booking_id=sample_booking.id,
            user_id=sample_user.id,
            simulate_status="FAILED",
        )
        assert payment.status == PaymentStatus.FAILED
        db_session.refresh(sample_booking)
        assert sample_booking.status == BookingStatus.FAILED

    def test_payment_wrong_user(self, db_session, sample_booking, second_user):
        service = PaymentService(db_session)
        with pytest.raises(ForbiddenError):
            service.process_payment(
                booking_id=sample_booking.id,
                user_id=second_user.id,
                simulate_status="SUCCESS",
            )

    def test_payment_nonexistent_booking(self, db_session, sample_user):
        service = PaymentService(db_session)
        with pytest.raises(NotFoundError):
            service.process_payment(
                booking_id=uuid.uuid4(),
                user_id=sample_user.id,
                simulate_status="SUCCESS",
            )

    def test_duplicate_payment_rejected(self, db_session, sample_booking, sample_user):
        service = PaymentService(db_session)
        service.process_payment(
            booking_id=sample_booking.id,
            user_id=sample_user.id,
            simulate_status="SUCCESS",
        )
        # Second payment should fail
        with pytest.raises((ConflictError, BadRequestError)):
            service.process_payment(
                booking_id=sample_booking.id,
                user_id=sample_user.id,
                simulate_status="SUCCESS",
            )

    def test_payment_non_pending_booking(self, db_session, sample_booking, sample_user):
        """Only PENDING bookings can be paid."""
        sample_booking.status = BookingStatus.CANCELLED
        db_session.flush()

        service = PaymentService(db_session)
        with pytest.raises(BadRequestError, match="Cannot pay"):
            service.process_payment(
                booking_id=sample_booking.id,
                user_id=sample_user.id,
                simulate_status="SUCCESS",
            )


class TestWebhookProcessing:
    def test_webhook_success(self, db_session, sample_booking):
        service = PaymentService(db_session)
        result = service.process_webhook(
            event_id="evt_test_001",
            booking_id=sample_booking.id,
            status="SUCCESS",
            amount=sample_booking.amount,
        )
        assert result["status"] == "SUCCESS"
        db_session.refresh(sample_booking)
        assert sample_booking.status == BookingStatus.CONFIRMED

    def test_webhook_failure(self, db_session, sample_booking):
        service = PaymentService(db_session)
        result = service.process_webhook(
            event_id="evt_test_002",
            booking_id=sample_booking.id,
            status="FAILED",
            amount=sample_booking.amount,
        )
        assert result["status"] == "FAILED"
        db_session.refresh(sample_booking)
        assert sample_booking.status == BookingStatus.FAILED

    def test_webhook_duplicate_idempotent(self, db_session, sample_booking):
        """Duplicate webhooks with same event_id must be safely ignored."""
        service = PaymentService(db_session)
        result1 = service.process_webhook(
            event_id="evt_dup_001",
            booking_id=sample_booking.id,
            status="SUCCESS",
            amount=sample_booking.amount,
        )
        # Second call with same event_id
        result2 = service.process_webhook(
            event_id="evt_dup_001",
            booking_id=sample_booking.id,
            status="SUCCESS",
            amount=sample_booking.amount,
        )
        assert "already processed" in result2["message"].lower()
        # Payment ID should be the same
        assert result2["payment_id"] == result1["payment_id"]

    def test_webhook_amount_mismatch(self, db_session, sample_booking):
        service = PaymentService(db_session)
        with pytest.raises(BadRequestError, match="mismatch"):
            service.process_webhook(
                event_id="evt_mismatch_001",
                booking_id=sample_booking.id,
                status="SUCCESS",
                amount=Decimal("999.99"),
            )

    def test_webhook_invalid_booking(self, db_session):
        service = PaymentService(db_session)
        with pytest.raises(NotFoundError):
            service.process_webhook(
                event_id="evt_notfound_001",
                booking_id=uuid.uuid4(),
                status="SUCCESS",
                amount=Decimal("500.00"),
            )

    def test_webhook_invalid_transition(self, db_session, sample_booking):
        """Cannot transition FAILED → CONFIRMED via webhook."""
        sample_booking.status = BookingStatus.FAILED
        db_session.flush()

        service = PaymentService(db_session)
        with pytest.raises(BadRequestError, match="Cannot transition"):
            service.process_webhook(
                event_id="evt_invalid_001",
                booking_id=sample_booking.id,
                status="SUCCESS",
                amount=sample_booking.amount,
            )
