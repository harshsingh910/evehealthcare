"""
Payment service — handles simulated payments and webhook processing.

CRITICAL DESIGN DECISIONS:

1. PAYMENT AMOUNT: Always derived from booking.amount, never from client.

2. DUPLICATE PAYMENT PREVENTION: Checks for existing payment before creating.
   Combined with booking_id UNIQUE constraint on payments table for race safety.

3. WEBHOOK IDEMPOTENCY: Uses provider_event_id with a UNIQUE database constraint.
   If two identical webhooks arrive simultaneously:
   - Both pass the application-level check (race window)
   - Only one INSERT succeeds; the other hits IntegrityError
   - The failing transaction is caught and returns safely

4. TRANSACTION ATOMICITY: Payment creation + booking status update happen
   in a single transaction. If either fails, both are rolled back.

5. STATE MACHINE ENFORCEMENT: Webhooks cannot transition bookings from
   invalid states (e.g., FAILED → CONFIRMED is rejected).

6. PAYMENT GATEWAY ABSTRACTION: PaymentService calls the PaymentGateway
   interface. The SimulatedPaymentGateway is the default; replace with
   StripeGateway / RazorpayGateway in production without changing this file.
"""

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus, ALLOWED_TRANSITIONS
from app.models.payment import Payment, PaymentStatus
from app.repositories.booking_repository import BookingRepository
from app.repositories.payment_repository import PaymentRepository
from app.integrations.payments.simulator import SimulatedPaymentGateway
from app.services.audit_service import AuditService
from app.models.audit_log import AuditEventType
from app.utils.exceptions import (
    NotFoundError,
    BadRequestError,
    ForbiddenError,
    ConflictError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.audit = AuditService(db)

    def process_payment(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        simulate_status: str,
    ) -> Payment:
        """
        Process a simulated payment for a booking.

        Flow:
          1. Lock booking row (prevent concurrent payment races)
          2. Validate ownership and state (must be PENDING)
          3. Prevent duplicate payments
          4. Call payment gateway (SimulatedPaymentGateway in this assignment)
          5. Create Payment record with gateway result
          6. Update Booking status atomically
        """
        # 1. Find booking with row lock to prevent concurrent payment race
        booking = self.booking_repo.get_by_id_for_update(booking_id)
        if not booking:
            raise NotFoundError(detail="Booking not found")

        # 2. Authorization: only booking owner can pay
        if booking.user_id != user_id:
            raise ForbiddenError(detail="You do not have access to this booking")

        # 3. Verify booking is payable (must be PENDING)
        if booking.status != BookingStatus.PENDING:
            raise BadRequestError(
                detail=f"Cannot pay for booking with status '{booking.status.value}'"
            )

        # 4. Prevent duplicate payments (application-level guard)
        existing_payment = self.payment_repo.get_by_booking_id(booking_id)
        if existing_payment:
            raise ConflictError(detail="Payment already exists for this booking")

        # 5. Call the payment gateway — pure simulation, no DB writes inside
        gateway = SimulatedPaymentGateway(simulate_status=simulate_status)
        gateway_result = gateway.charge(
            amount=booking.amount,
            currency="INR",
            reference=str(booking_id),
        )

        # 6. Map gateway result to internal status
        payment_status = (
            PaymentStatus.SUCCESS if gateway_result.success else PaymentStatus.FAILED
        )

        # 7. Create payment record with provider_event_id from gateway
        payment = Payment(
            booking_id=booking_id,
            amount=booking.amount,
            status=payment_status,
            provider_event_id=gateway_result.provider_event_id,
        )
        self.payment_repo.create(payment)

        # 8. Update booking status atomically
        booking.status = (
            BookingStatus.CONFIRMED if gateway_result.success else BookingStatus.FAILED
        )

        # 9. Audit event
        self.audit.log(
            event_type=(
                AuditEventType.PAYMENT_SUCCESS
                if gateway_result.success
                else AuditEventType.PAYMENT_FAILED
            ),
            actor_user_id=user_id,
            entity_type="payment",
            entity_id=str(payment.id),
            metadata={
                "booking_id": str(booking_id),
                "amount": str(booking.amount),
                "provider_event_id": gateway_result.provider_event_id,
                "status": payment_status.value,
            },
        )

        # 10. Commit payment, booking update, and audit log in one transaction
        try:
            self.db.commit()
            self.db.refresh(payment)
            self.db.refresh(booking)
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(detail="Payment already exists for this booking")

        logger.info(
            "Payment processed",
            extra={
                "event": "payment_processed",
                "booking_id": str(booking_id),
                "payment_id": str(payment.id),
                "status": payment_status.value,
                "provider_event_id": gateway_result.provider_event_id,
            },
        )
        return payment

    def process_webhook(
        self,
        event_id: str,
        booking_id: uuid.UUID,
        status: str,
        amount: Decimal,
    ) -> dict:
        """
        Process an external payment webhook idempotently.

        IDEMPOTENCY STRATEGY:
        1. Application check: if provider_event_id already exists, return early
        2. Database constraint: UNIQUE on provider_event_id catches races
        3. Transaction: payment + booking update are atomic
        """
        # 1. Idempotency check — fast path for duplicate webhooks
        existing = self.payment_repo.get_by_provider_event_id(event_id)
        if existing:
            self.audit.log(
                event_type=AuditEventType.WEBHOOK_DUPLICATE,
                entity_type="payment",
                entity_id=str(existing.id),
                metadata={"event_id": event_id},
            )
            logger.info(
                "Duplicate webhook ignored",
                extra={"event": "webhook_duplicate", "event_id": event_id},
            )
            return {
                "message": "Event already processed",
                "payment_id": existing.id,
                "status": existing.status.value,
            }

        # 2. Find and lock booking
        booking = self.booking_repo.get_by_id_for_update(booking_id)
        if not booking:
            raise NotFoundError(detail="Booking not found")

        # 3. Validate amount matches booking amount
        if amount != booking.amount:
            raise BadRequestError(
                detail=f"Amount mismatch: webhook={amount}, booking={booking.amount}"
            )

        # 4. Determine target booking status
        payment_status = (
            PaymentStatus.SUCCESS if status == "SUCCESS" else PaymentStatus.FAILED
        )
        target_booking_status = (
            BookingStatus.CONFIRMED
            if payment_status == PaymentStatus.SUCCESS
            else BookingStatus.FAILED
        )

        # 5. Enforce state machine — reject invalid transitions
        if target_booking_status not in ALLOWED_TRANSITIONS.get(booking.status, set()):
            raise BadRequestError(
                detail=f"Cannot transition booking from '{booking.status.value}' to '{target_booking_status.value}'"
            )

        # 6. Check for existing payment on this booking
        existing_payment = self.payment_repo.get_by_booking_id(booking_id)
        if existing_payment:
            raise ConflictError(detail="Payment already exists for this booking")

        # 7. Create payment with provider_event_id for idempotency
        payment = Payment(
            booking_id=booking_id,
            amount=booking.amount,
            status=payment_status,
            provider_event_id=event_id,
        )
        self.payment_repo.create(payment)

        # 8. Update booking status
        booking.status = target_booking_status

        # 9. Audit event
        self.audit.log(
            event_type=AuditEventType.WEBHOOK_PROCESSED,
            actor_user_id=booking.user_id,
            entity_type="payment",
            entity_id=str(payment.id),
            metadata={
                "event_id": event_id,
                "booking_id": str(booking_id),
                "amount": str(amount),
                "status": payment_status.value,
            },
        )

        # 10. Atomic commit — if UNIQUE constraint fails, handle gracefully
        try:
            self.db.commit()
            self.db.refresh(payment)

        except IntegrityError:
            self.db.rollback()
            # Race condition: another request already processed this event
            existing = self.payment_repo.get_by_provider_event_id(event_id)
            if existing:
                return {
                    "message": "Event already processed (concurrent)",
                    "payment_id": existing.id,
                    "status": existing.status.value,
                }
            raise ConflictError(detail="Payment conflict")

        logger.info(
            "Webhook processed",
            extra={
                "event": "webhook_processed",
                "event_id": event_id,
                "booking_id": str(booking_id),
                "payment_id": str(payment.id),
                "status": payment_status.value,
            },
        )
        return {
            "message": "Payment processed successfully",
            "payment_id": payment.id,
            "status": payment_status.value,
        }
