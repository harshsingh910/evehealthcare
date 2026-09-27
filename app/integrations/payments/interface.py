"""
Payment Gateway Interface.

Defines the abstract contract that any payment provider must implement.
This allows the simulated gateway used in development/testing to be
swapped for a real provider (Stripe, Razorpay, etc.) in production
without touching the PaymentService business logic.

DESIGN RATIONALE:
- Protocol (structural subtyping) instead of ABC avoids inheritance coupling.
- The interface is intentionally minimal — only what PaymentService needs.
- No database writes, no booking updates — those stay in PaymentService.
"""

from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GatewayChargeResult:
    """
    Result returned by a payment gateway charge attempt.

    Attributes:
        success:          True if the charge succeeded.
        provider_event_id: Unique event/charge ID from the provider.
                          Used for webhook idempotency.
        gateway_status:   Raw status string from the provider
                          (e.g. "SUCCESS", "FAILED", "DECLINED").
        error_message:    Human-readable failure reason (None on success).
    """
    success: bool
    provider_event_id: str
    gateway_status: str
    error_message: str | None = None


@runtime_checkable
class PaymentGateway(Protocol):
    """
    Abstract payment gateway protocol.

    Any class implementing this protocol can be used as a payment gateway.
    Python's structural subtyping means no explicit inheritance is required.

    To integrate a real provider (e.g. Stripe):
        class StripeGateway:
            def charge(self, amount, currency, reference) -> GatewayChargeResult:
                # call stripe.PaymentIntent.create(...)
    """

    def charge(
        self,
        amount: Decimal,
        currency: str,
        reference: str,
    ) -> GatewayChargeResult:
        """
        Attempt to charge the given amount.

        Args:
            amount:    Charge amount (Decimal, e.g. Decimal("500.00")).
            currency:  ISO 4217 currency code (e.g. "INR").
            reference: Unique booking reference for idempotency.

        Returns:
            GatewayChargeResult describing the outcome.
        """
        ...
