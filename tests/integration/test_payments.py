"""Integration tests for Payments endpoints."""

import uuid
import pytest


class TestSimulatedPayment:
    def test_payment_success(self, client, auth_headers, sample_booking):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "SUCCESS",
        }, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert float(data["amount"]) == float(sample_booking.amount)

    def test_payment_failed(self, client, auth_headers, sample_booking):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "FAILED",
        }, headers=auth_headers)
        assert response.status_code == 201
        assert response.json()["status"] == "FAILED"

    def test_payment_unauthenticated(self, client, sample_booking):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "SUCCESS",
        })
        assert response.status_code == 401

    def test_payment_wrong_user(self, client, second_auth_headers, sample_booking):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "SUCCESS",
        }, headers=second_auth_headers)
        assert response.status_code == 403

    def test_payment_invalid_booking(self, client, auth_headers):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(uuid.uuid4()),
            "simulate_status": "SUCCESS",
        }, headers=auth_headers)
        assert response.status_code == 404

    def test_payment_invalid_status(self, client, auth_headers, sample_booking):
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "INVALID",
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_duplicate_payment(self, client, auth_headers, sample_booking):
        client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "SUCCESS",
        }, headers=auth_headers)
        response = client.post("/api/v1/payments", json={
            "booking_id": str(sample_booking.id),
            "simulate_status": "SUCCESS",
        }, headers=auth_headers)
        # Should be 400 or 409 — not 201
        assert response.status_code in (400, 409)
