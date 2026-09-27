"""
Payments router — simulated payment processing and webhook endpoint.

Two entry points for payment processing:
1. POST /payments — User-initiated simulated payment (requires auth)
2. POST /payments/webhook — External provider callback (idempotent, no auth)

RATE LIMITING:
POST /payments is rate-limited per authenticated user to prevent payment
flooding/abuse. The limit is separate and configurable from the login limit.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.payment_service import PaymentService
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentResponse,
    WebhookRequest,
    WebhookResponse,
)
from app.core.config import settings
from app.utils.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


def _check_payment_rate_limit(user_id: str) -> None:
    """
    Rate limit payment creation per authenticated user.

    Keyed by user ID (not IP) so VPN/proxy rotation doesn't bypass the limit.
    If Redis is unavailable, this is bypassed gracefully.
    """
    key = f"rate_limit:payment:{user_id}"
    check_rate_limit(
        key=key,
        max_attempts=settings.RATE_LIMIT_PAYMENT_ATTEMPTS,
        window_seconds=settings.RATE_LIMIT_PAYMENT_WINDOW_SECONDS,
        identifier=user_id,
    )


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process simulated payment",
    description=(
        "Simulate a payment for a booking. The amount is derived from the booking, "
        "not from the request. Use simulate_status=SUCCESS or FAILED for deterministic testing. "
        "Rate-limited per user to prevent abuse."
    ),
)
def create_payment(
    body: PaymentCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_payment_rate_limit(str(current_user.id))
    service = PaymentService(db)
    payment = service.process_payment(
        booking_id=body.booking_id,
        user_id=current_user.id,
        simulate_status=body.simulate_status,
    )
    return payment


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Payment webhook (idempotent)",
    description=(
        "Receives payment status updates from an external provider. "
        "IDEMPOTENT: duplicate event_ids are safely ignored using a UNIQUE "
        "database constraint on provider_event_id. "
        "Amount must match the booking amount."
    ),
)
def payment_webhook(body: WebhookRequest, db: Session = Depends(get_db)):
    service = PaymentService(db)
    result = service.process_webhook(
        event_id=body.event_id,
        booking_id=body.booking_id,
        status=body.status,
        amount=body.amount,
    )
    return result
