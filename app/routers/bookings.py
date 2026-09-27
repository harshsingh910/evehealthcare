"""
Bookings router — authenticated booking CRUD with authorization.

All endpoints require JWT authentication.
Users can only see and modify their own bookings.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.booking_service import BookingService
from app.schemas.booking import BookingCreateRequest, BookingResponse, BookingListResponse
from app.utils.pagination import MAX_PAGE_SIZE

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a diagnostic test booking",
    description=(
        "Book a diagnostic test at a centre. Amount is derived server-side from "
        "centre_test pricing — clients cannot manipulate the price. "
        "Appointment must be in the future."
    ),
)
def create_booking(
    body: BookingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    booking = service.create_booking(
        user_id=current_user.id,
        centre_id=body.centre_id,
        test_id=body.test_id,
        appointment_datetime=body.appointment_datetime,
    )
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        centre_id=booking.centre_id,
        test_id=booking.test_id,
        appointment_datetime=booking.appointment_datetime,
        amount=booking.amount,
        status=booking.status.value,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


@router.get(
    "",
    response_model=BookingListResponse,
    summary="List your bookings",
    description="Returns a paginated list of your bookings only.",
)
def list_bookings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    return service.list_user_bookings(
        user_id=current_user.id, page=page, page_size=page_size
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get booking details",
    description="Returns booking details. Only the booking owner can access.",
)
def get_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    booking = service.get_booking(booking_id=booking_id, user_id=current_user.id)
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        centre_id=booking.centre_id,
        test_id=booking.test_id,
        appointment_datetime=booking.appointment_datetime,
        amount=booking.amount,
        status=booking.status.value,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        centre_name=booking.centre.name if booking.centre else None,
        test_name=booking.test.name if booking.test else None,
    )


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    description=(
        "Cancel a PENDING or CONFIRMED booking. "
        "FAILED and CANCELLED bookings cannot be cancelled."
    ),
)
def cancel_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = BookingService(db)
    booking = service.cancel_booking(booking_id=booking_id, user_id=current_user.id)
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        centre_id=booking.centre_id,
        test_id=booking.test_id,
        appointment_datetime=booking.appointment_datetime,
        amount=booking.amount,
        status=booking.status.value,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )
