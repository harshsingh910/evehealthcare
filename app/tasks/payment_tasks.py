"""
Payment background tasks.

Processes webhook events asynchronously with retry and idempotency.
Uses bounded exponential backoff for transient failures.

IDEMPOTENCY: The underlying PaymentService.process_webhook() is idempotent
via the UNIQUE constraint on provider_event_id. Safe to retry without
creating duplicate payments.
"""

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.payment_service import PaymentService
from app.core.logging import get_logger
from decimal import Decimal

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    acks_late=True,
    name="app.tasks.payment_tasks.process_webhook_async",
)
def process_webhook_async(
    self,
    event_id: str,
    booking_id: str,
    status: str,
    amount: str,
):
    """
    Process a payment webhook event asynchronously.

    Uses exponential backoff: 10s, 20s, 40s, 80s, 160s
    Permanently invalid events (NotFound, BadRequest) are NOT retried.
    Only transient failures (DB errors, connection issues) are retried.
    """
    logger.info(
        "Processing webhook async",
        extra={
            "event": "webhook_task_started",
            "event_id": event_id,
            "booking_id": booking_id,
        },
    )

    db = SessionLocal()
    try:
        service = PaymentService(db)
        result = service.process_webhook(
            event_id=event_id,
            booking_id=booking_id,
            status=status,
            amount=Decimal(amount),
        )
        logger.info(
            "Webhook task completed",
            extra={
                "event": "webhook_task_completed",
                "event_id": event_id,
                "result": str(result),
            },
        )
        return result
    except Exception as exc:
        # Don't retry business logic errors (404, 400, 409)
        from app.utils.exceptions import NotFoundError, BadRequestError, ConflictError

        if isinstance(exc, (NotFoundError, BadRequestError, ConflictError)):
            logger.warning(
                f"Webhook task failed permanently: {exc.detail}",
                extra={"event": "webhook_task_permanent_failure", "event_id": event_id},
            )
            return {"error": exc.detail, "retryable": False}

        # Retry transient failures with exponential backoff
        logger.error(
            f"Webhook task transient failure: {exc}",
            extra={"event": "webhook_task_transient_failure", "event_id": event_id},
        )
        raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
    finally:
        db.close()
