"""
Notification tasks (simulated).

In production, these would send emails/SMS for booking confirmations,
payment receipts, and appointment reminders.
"""

from app.tasks.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.notification_tasks.send_booking_confirmation",
)
def send_booking_confirmation(self, booking_id: str, user_email: str):
    """
    Simulate sending a booking confirmation notification.

    In production: integrate with email service (SendGrid, SES, etc.)
    """
    logger.info(
        "Sending booking confirmation (simulated)",
        extra={
            "event": "notification_booking_confirmation",
            "booking_id": booking_id,
            "user_email": user_email,
        },
    )
    # Simulated — no actual email sent
    return {"sent": True, "booking_id": booking_id, "email": user_email}


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.notification_tasks.send_payment_receipt",
)
def send_payment_receipt(self, payment_id: str, user_email: str):
    """Simulate sending a payment receipt notification."""
    logger.info(
        "Sending payment receipt (simulated)",
        extra={
            "event": "notification_payment_receipt",
            "payment_id": payment_id,
            "user_email": user_email,
        },
    )
    return {"sent": True, "payment_id": payment_id, "email": user_email}
