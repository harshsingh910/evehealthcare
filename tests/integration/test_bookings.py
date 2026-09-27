"""Integration tests for Bookings endpoints."""

import uuid
import pytest


class TestCreateBooking:
    def test_create_booking_success(self, client, auth_headers, sample_centre, sample_test, sample_centre_test, future_datetime):
        response = client.post("/api/v1/bookings", json={
            "centre_id": str(sample_centre.id),
            "test_id": str(sample_test.id),
            "appointment_datetime": future_datetime,
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"
        assert float(data["amount"]) == float(sample_centre_test.price)

    def test_create_booking_unauthenticated(self, client, sample_centre, sample_test, future_datetime):
        response = client.post("/api/v1/bookings", json={
            "centre_id": str(sample_centre.id),
            "test_id": str(sample_test.id),
            "appointment_datetime": future_datetime,
        })
        assert response.status_code == 401

    def test_create_booking_invalid_centre(self, client, auth_headers, sample_test, future_datetime):
        response = client.post("/api/v1/bookings", json={
            "centre_id": str(uuid.uuid4()),
            "test_id": str(sample_test.id),
            "appointment_datetime": future_datetime,
        }, headers=auth_headers)
        assert response.status_code == 404

    def test_create_booking_invalid_test(self, client, auth_headers, sample_centre, future_datetime):
        response = client.post("/api/v1/bookings", json={
            "centre_id": str(sample_centre.id),
            "test_id": str(uuid.uuid4()),
            "appointment_datetime": future_datetime,
        }, headers=auth_headers)
        assert response.status_code == 404

    def test_create_booking_past_appointment(self, client, auth_headers, sample_centre, sample_test, sample_centre_test, past_datetime):
        response = client.post("/api/v1/bookings", json={
            "centre_id": str(sample_centre.id),
            "test_id": str(sample_test.id),
            "appointment_datetime": past_datetime,
        }, headers=auth_headers)
        assert response.status_code == 400


class TestListBookings:
    def test_list_own_bookings(self, client, auth_headers, sample_booking):
        response = client.get("/api/v1/bookings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1


class TestGetBooking:
    def test_get_own_booking(self, client, auth_headers, sample_booking):
        response = client.get(f"/api/v1/bookings/{sample_booking.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_booking.id)

    def test_get_other_users_booking(self, client, second_auth_headers, sample_booking):
        """User B cannot access User A's booking."""
        response = client.get(
            f"/api/v1/bookings/{sample_booking.id}",
            headers=second_auth_headers,
        )
        assert response.status_code == 403

    def test_get_nonexistent_booking(self, client, auth_headers):
        response = client.get(f"/api/v1/bookings/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404


class TestCancelBooking:
    def test_cancel_pending_booking(self, client, auth_headers, sample_booking):
        response = client.post(
            f"/api/v1/bookings/{sample_booking.id}/cancel",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cancel_other_users_booking(self, client, second_auth_headers, sample_booking):
        response = client.post(
            f"/api/v1/bookings/{sample_booking.id}/cancel",
            headers=second_auth_headers,
        )
        assert response.status_code == 403
