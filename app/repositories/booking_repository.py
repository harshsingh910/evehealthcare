"""Booking repository — data access for bookings."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def get_by_id(self, booking_id: uuid.UUID) -> Optional[Booking]:
        return (
            self.db.query(Booking)
            .options(
                joinedload(Booking.centre),
                joinedload(Booking.test),
                joinedload(Booking.payment),
            )
            .filter(Booking.id == booking_id)
            .first()
        )

    def get_by_id_for_update(self, booking_id: uuid.UUID) -> Optional[Booking]:
        """
        Get booking with FOR UPDATE lock for transactional safety.

        Used during payment and webhook processing to prevent
        concurrent modifications from corrupting state.

        Falls back to regular query on databases that don't support
        SELECT FOR UPDATE (e.g., SQLite in tests).
        """
        query = self.db.query(Booking).filter(Booking.id == booking_id)
        try:
            return query.with_for_update().first()
        except Exception:
            # SQLite doesn't support FOR UPDATE — fall back to regular query
            return query.first()

    def get_user_bookings_query(self, user_id: uuid.UUID):
        """Query for a user's bookings, for pagination."""
        return (
            select(Booking)
            .filter(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )

    def save(self, booking: Booking) -> Booking:
        """Persist changes to an existing booking."""
        self.db.commit()
        self.db.refresh(booking)
        return booking
