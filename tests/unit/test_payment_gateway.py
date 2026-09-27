"""Unit tests for payment gateway abstraction and simulator."""

from decimal import Decimal
import pytest

from app.integrations.payments.interface import PaymentGateway, GatewayChargeResult
from app.integrations.payments.simulator import SimulatedPaymentGateway


def test_simulated_gateway_implements_protocol():
    """Verify SimulatedPaymentGateway satisfies PaymentGateway Protocol."""
    gateway = SimulatedPaymentGateway(simulate_status="SUCCESS")
    assert isinstance(gateway, PaymentGateway)


def test_simulated_gateway_charge_success():
    """Verify SUCCESS charge returns correct result structure."""
    gateway = SimulatedPaymentGateway(simulate_status="SUCCESS")
    result = gateway.charge(
        amount=Decimal("750.00"),
        currency="INR",
        reference="booking-test-123",
    )
    assert isinstance(result, GatewayChargeResult)
    assert result.success is True
    assert result.gateway_status == "SUCCESS"
    assert result.error_message is None
    assert result.provider_event_id.startswith("sim_")


def test_simulated_gateway_charge_failed():
    """Verify FAILED charge returns failed outcome with error message."""
    gateway = SimulatedPaymentGateway(simulate_status="FAILED")
    result = gateway.charge(
        amount=Decimal("750.00"),
        currency="INR",
        reference="booking-test-456",
    )
    assert isinstance(result, GatewayChargeResult)
    assert result.success is False
    assert result.gateway_status == "FAILED"
    assert result.error_message == "Simulated payment failure"
    assert result.provider_event_id.startswith("sim_")


def test_simulated_gateway_invalid_status():
    """Verify ValueError is raised if invalid simulate_status is provided."""
    with pytest.raises(ValueError) as exc_info:
        SimulatedPaymentGateway(simulate_status="PENDING")
    assert "Invalid simulate_status" in str(exc_info.value)


def test_simulated_gateway_unique_event_ids():
    """Verify each charge produces a unique provider event ID."""
    gateway = SimulatedPaymentGateway(simulate_status="SUCCESS")
    res1 = gateway.charge(Decimal("100.00"), "INR", "ref1")
    res2 = gateway.charge(Decimal("100.00"), "INR", "ref2")
    assert res1.provider_event_id != res2.provider_event_id
