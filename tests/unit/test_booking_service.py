"""Unit tests for BookingService."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.booking import Booking, BookingStatus
from app.models.diagnostic_centre import DiagnosticCentre
from app.models.diagnostic_test import DiagnosticTest
from app.models.centre_test import CentreTest
from app.services.booking_service import BookingService
from app.utils.exceptions import NotFoundError, BadRequestError, ForbiddenError


class TestBookingCreation:
    def test_create_booking_derives_price(self, db_session, sample_user, sample_centre, sample_test, sample_centre_test):
        """Amount must come from centre_test price, not from client."""
        service = BookingService(db_session)
        booking = service.create_booking(
            user_id=sample_user.id,
            centre_id=sample_centre.id,
            test_id=sample_test.id,
            appointment_datetime=datetime.now(timezone.utc) + timedelta(days=7),
        )
        assert booking.amount == sample_centre_test.price
        assert booking.status == BookingStatus.PENDING

    def test_create_booking_invalid_centre(self, db_session, sample_user):
        service = BookingService(db_session)
        with pytest.raises(NotFoundError, match="centre not found"):
            service.create_booking(
                user_id=sample_user.id,
                centre_id=uuid.uuid4(),
                test_id=uuid.uuid4(),
                appointment_datetime=datetime.now(timezone.utc) + timedelta(days=7),
            )

    def test_create_booking_invalid_test(self, db_session, sample_user, sample_centre):
        service = BookingService(db_session)
        with pytest.raises(NotFoundError, match="test not found"):
            service.create_booking(
                user_id=sample_user.id,
                centre_id=sample_centre.id,
                test_id=uuid.uuid4(),
                appointment_datetime=datetime.now(timezone.utc) + timedelta(days=7),
            )

    def test_create_booking_test_not_at_centre(self, db_session, sample_user, sample_centre):
        """Test exists but is not offered at this centre."""
        other_test = DiagnosticTest(name="Other Test", description="Not offered here")
        db_session.add(other_test)
        db_session.flush()

        service = BookingService(db_session)
        with pytest.raises(BadRequestError, match="not offered"):
            service.create_booking(
                user_id=sample_user.id,
                centre_id=sample_centre.id,
                test_id=other_test.id,
                appointment_datetime=datetime.now(timezone.utc) + timedelta(days=7),
            )

    def test_create_booking_past_appointment(self, db_session, sample_user, sample_centre, sample_test, sample_centre_test):
        service = BookingService(db_session)
        with pytest.raises(BadRequestError, match="future"):
            service.create_booking(
                user_id=sample_user.id,
                centre_id=sample_centre.id,
                test_id=sample_test.id,
                appointment_datetime=datetime.now(timezone.utc) - timedelta(days=1),
            )


class TestBookingAuthorization:
    def test_user_cannot_access_others_booking(self, db_session, sample_booking, second_user):
        service = BookingService(db_session)
        with pytest.raises(ForbiddenError):
            service.get_booking(
                booking_id=sample_booking.id,
                user_id=second_user.id,
            )

    def test_user_can_access_own_booking(self, db_session, sample_booking, sample_user):
        service = BookingService(db_session)
        booking = service.get_booking(
            booking_id=sample_booking.id,
            user_id=sample_user.id,
        )
        assert booking.id == sample_booking.id


class TestBookingCancellation:
    def test_cancel_pending_booking(self, db_session, sample_booking, sample_user):
        service = BookingService(db_session)
        booking = service.cancel_booking(
            booking_id=sample_booking.id,
            user_id=sample_user.id,
        )
        assert booking.status == BookingStatus.CANCELLED

    def test_cancel_failed_booking_rejected(self, db_session, sample_booking, sample_user):
        """FAILED bookings cannot be cancelled — state machine enforcement."""
        sample_booking.status = BookingStatus.FAILED
        db_session.flush()

        service = BookingService(db_session)
        with pytest.raises(BadRequestError, match="Cannot cancel"):
            service.cancel_booking(
                booking_id=sample_booking.id,
                user_id=sample_user.id,
            )

    def test_cancel_other_users_booking(self, db_session, sample_booking, second_user):
        service = BookingService(db_session)
        with pytest.raises(ForbiddenError):
            service.cancel_booking(
                booking_id=sample_booking.id,
                user_id=second_user.id,
            )
