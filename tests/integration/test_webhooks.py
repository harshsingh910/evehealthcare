"""Integration tests for Webhook endpoints."""

import uuid
import pytest


class TestWebhook:
    def test_webhook_success(self, client, sample_booking):
        response = client.post("/api/v1/payments/webhook", json={
            "event_id": "evt_integ_001",
            "booking_id": str(sample_booking.id),
            "status": "SUCCESS",
            "amount": float(sample_booking.amount),
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"

    def test_webhook_failed(self, client, sample_booking):
        response = client.post("/api/v1/payments/webhook", json={
            "event_id": "evt_integ_002",
            "booking_id": str(sample_booking.id),
            "status": "FAILED",
            "amount": float(sample_booking.amount),
        })
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

    def test_webhook_duplicate_idempotent(self, client, sample_booking):
        """Same event_id sent twice — second should be safely ignored."""
        payload = {
            "event_id": "evt_integ_dup",
            "booking_id": str(sample_booking.id),
            "status": "SUCCESS",
            "amount": float(sample_booking.amount),
        }
        resp1 = client.post("/api/v1/payments/webhook", json=payload)
        assert resp1.status_code == 200

        resp2 = client.post("/api/v1/payments/webhook", json=payload)
        assert resp2.status_code == 200
        assert "already processed" in resp2.json()["message"].lower()

    def test_webhook_amount_mismatch(self, client, sample_booking):
        response = client.post("/api/v1/payments/webhook", json={
            "event_id": "evt_integ_mismatch",
            "booking_id": str(sample_booking.id),
            "status": "SUCCESS",
            "amount": 99999.99,
        })
        assert response.status_code == 400

    def test_webhook_invalid_booking(self, client):
        response = client.post("/api/v1/payments/webhook", json={
            "event_id": "evt_integ_notfound",
            "booking_id": str(uuid.uuid4()),
            "status": "SUCCESS",
            "amount": 500.00,
        })
        assert response.status_code == 404

    def test_webhook_missing_event_id(self, client, sample_booking):
        response = client.post("/api/v1/payments/webhook", json={
            "booking_id": str(sample_booking.id),
            "status": "SUCCESS",
            "amount": float(sample_booking.amount),
        })
        assert response.status_code == 422

    def test_webhook_invalid_status(self, client, sample_booking):
        response = client.post("/api/v1/payments/webhook", json={
            "event_id": "evt_integ_badstatus",
            "booking_id": str(sample_booking.id),
            "status": "PARTIAL",
            "amount": float(sample_booking.amount),
        })
        assert response.status_code == 422

    def test_webhook_does_not_create_duplicate_payment(self, client, sample_booking):
        """Duplicate webhook must not create duplicate payment records."""
        payload = {
            "event_id": "evt_integ_nodup",
            "booking_id": str(sample_booking.id),
            "status": "SUCCESS",
            "amount": float(sample_booking.amount),
        }
        resp1 = client.post("/api/v1/payments/webhook", json=payload)
        resp2 = client.post("/api/v1/payments/webhook", json=payload)

        # Same payment_id must be returned both times
        assert resp1.json()["payment_id"] == resp2.json()["payment_id"]
