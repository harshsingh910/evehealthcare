"""Payment repository — data access for payments."""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_booking_id(self, booking_id: uuid.UUID) -> Optional[Payment]:
        return self.db.query(Payment).filter(
            Payment.booking_id == booking_id
        ).first()

    def get_by_provider_event_id(self, event_id: str) -> Optional[Payment]:
        return self.db.query(Payment).filter(
            Payment.provider_event_id == event_id
        ).first()

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        # Don't commit here — let the service layer manage the transaction
        # so payment + booking status update are atomic
        return payment

    def save(self, payment: Payment) -> Payment:
        self.db.commit()
        self.db.refresh(payment)
        return payment
