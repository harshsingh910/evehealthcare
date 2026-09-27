"""
Simulated Payment Gateway.

Deterministic, in-process payment simulator used instead of a real
payment provider. The `simulate_status` parameter drives the outcome —
"SUCCESS" charges succeed; anything else fails.

DESIGN:
- No database access — pure logic, easy to test in isolation.
- No booking state changes — that is PaymentService's responsibility.
- No authorization — PaymentService validates ownership.
- Deterministic — behaviour is controlled by the caller for testing.
- Generates a unique provider_event_id per charge to mimic a real provider.

REPLACING WITH A REAL PROVIDER:
Create a class (e.g. StripeGateway, RazorpayGateway) that satisfies
the PaymentGateway Protocol in interface.py and pass it to PaymentService.
No other code changes are required.
"""

import uuid
from decimal import Decimal

from app.integrations.payments.interface import GatewayChargeResult
from app.core.logging import get_logger

logger = get_logger(__name__)

# Valid simulated outcomes — maps to GatewayChargeResult.success
_SUCCESS_STATUS = "SUCCESS"
_FAILED_STATUS = "FAILED"
VALID_SIMULATE_STATUSES = {_SUCCESS_STATUS, _FAILED_STATUS}


class SimulatedPaymentGateway:
    """
    Simulated payment gateway for development and testing.

    Implements the PaymentGateway Protocol (interface.py) so it can be
    passed to PaymentService without any changes to business logic.

    Usage:
        gateway = SimulatedPaymentGateway(simulate_status="SUCCESS")
        result = gateway.charge(amount=Decimal("500.00"), currency="INR", reference="booking-uuid")
        assert result.success
    """

    def __init__(self, simulate_status: str) -> None:
        """
        Args:
            simulate_status: "SUCCESS" or "FAILED".

        Raises:
            ValueError: If simulate_status is not a recognised value.
        """
        if simulate_status not in VALID_SIMULATE_STATUSES:
            raise ValueError(
                f"Invalid simulate_status '{simulate_status}'. "
                f"Must be one of: {sorted(VALID_SIMULATE_STATUSES)}"
            )
        self._simulate_status = simulate_status

    def charge(
        self,
        amount: Decimal,
        currency: str,
        reference: str,
    ) -> GatewayChargeResult:
        """
        Simulate a payment charge deterministically.

        The outcome is entirely determined by the simulate_status passed
        at construction — this makes tests predictable and fast.

        Args:
            amount:    Amount to charge (unused in simulation but present
                       for interface compatibility).
            currency:  Currency code (unused in simulation).
            reference: Booking reference (used as log context).

        Returns:
            GatewayChargeResult with success=True or success=False.
        """
        # Generate a provider-style event ID (mimics real provider UUID/token)
        provider_event_id = f"sim_{uuid.uuid4().hex}"
        success = self._simulate_status == _SUCCESS_STATUS

        logger.info(
            "Simulated payment gateway charge",
            extra={
                "event": "gateway_charge",
                "provider_event_id": provider_event_id,
                "reference": reference,
                "simulate_status": self._simulate_status,
                "success": success,
            },
        )

        if success:
            return GatewayChargeResult(
                success=True,
                provider_event_id=provider_event_id,
                gateway_status="SUCCESS",
            )
        else:
            return GatewayChargeResult(
                success=False,
                provider_event_id=provider_event_id,
                gateway_status="FAILED",
                error_message="Simulated payment failure",
            )
