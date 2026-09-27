"""
Booking service — core business logic for diagnostic test bookings.

KEY DESIGN DECISIONS:
1. Amount is derived from CentreTest.price, never trusted from client
2. Appointment datetime must be in the future
3. State transitions follow an explicit state machine
4. Authorization is checked — users can only see/modify their own bookings
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus, ALLOWED_TRANSITIONS
from app.repositories.booking_repository import BookingRepository
from app.repositories.centre_repository import CentreRepository
from app.repositories.test_repository import TestRepository
from app.utils.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.utils.pagination import paginate, build_paginated_response
from app.schemas.booking import BookingResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.centre_repo = CentreRepository(db)
        self.test_repo = TestRepository(db)

    def create_booking(
        self,
        user_id: uuid.UUID,
        centre_id: uuid.UUID,
        test_id: uuid.UUID,
        appointment_datetime: datetime,
    ) -> Booking:
        """
        Create a new booking.

        Validates centre, test, centre-test combination, appointment time,
        and derives the amount from the database.
        """
        # 1. Validate centre exists
        centre = self.centre_repo.get_by_id(centre_id)
        if not centre:
            raise NotFoundError(detail="Diagnostic centre not found")

        # 2. Validate test exists
        test = self.test_repo.get_by_id(test_id)
        if not test:
            raise NotFoundError(detail="Diagnostic test not found")

        # 3. Validate the centre offers this test
        centre_test = self.test_repo.get_centre_test(centre_id, test_id)
        if not centre_test:
            raise BadRequestError(
                detail=f"Test '{test.name}' is not offered at centre '{centre.name}'"
            )

        # 4. Validate appointment is in the future
        now = datetime.now(timezone.utc)
        if appointment_datetime.tzinfo is None:
            appointment_datetime = appointment_datetime.replace(tzinfo=timezone.utc)
        if appointment_datetime <= now:
            raise BadRequestError(detail="Appointment datetime must be in the future")

        # 5. Create booking with server-derived amount
        booking = Booking(
            user_id=user_id,
            centre_id=centre_id,
            test_id=test_id,
            appointment_datetime=appointment_datetime,
            amount=centre_test.price,  # Price from DB, not from client
            status=BookingStatus.PENDING,
        )
        booking = self.booking_repo.create(booking)

        logger.info(
            "Booking created",
            extra={
                "event": "booking_created",
                "booking_id": str(booking.id),
                "user_id": str(user_id),
                "amount": str(centre_test.price),
            },
        )
        return booking

    def get_booking(self, booking_id: uuid.UUID, user_id: uuid.UUID) -> Booking:
        """Get a booking, enforcing ownership authorization."""
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail="Booking not found")

        # Authorization: users can only see their own bookings
        if booking.user_id != user_id:
            raise ForbiddenError(detail="You do not have access to this booking")

        return booking

    def list_user_bookings(self, user_id: uuid.UUID, page: int, page_size: int) -> dict:
        """List bookings for the authenticated user only."""
        query = self.booking_repo.get_user_bookings_query(user_id)
        items, total = paginate(self.db, query, page, page_size)

        serialized = []
        for b in items:
            resp = BookingResponse(
                id=b.id,
                user_id=b.user_id,
                centre_id=b.centre_id,
                test_id=b.test_id,
                appointment_datetime=b.appointment_datetime,
                amount=b.amount,
                status=b.status.value,
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
            serialized.append(resp)

        return build_paginated_response(serialized, page, page_size, total)

    def cancel_booking(self, booking_id: uuid.UUID, user_id: uuid.UUID) -> Booking:
        """
        Cancel a booking, enforcing state machine rules.

        Only PENDING and CONFIRMED bookings can be cancelled.
        FAILED and CANCELLED bookings cannot be cancelled again.
        """
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(detail="Booking not found")

        if booking.user_id != user_id:
            raise ForbiddenError(detail="You do not have access to this booking")

        # Enforce state machine
        if BookingStatus.CANCELLED not in ALLOWED_TRANSITIONS.get(booking.status, set()):
            raise BadRequestError(
                detail=f"Cannot cancel booking with status '{booking.status.value}'"
            )

        booking.status = BookingStatus.CANCELLED
        booking = self.booking_repo.save(booking)

        logger.info(
            "Booking cancelled",
            extra={
                "event": "booking_cancelled",
                "booking_id": str(booking.id),
                "user_id": str(user_id),
            },
        )
        return booking
