from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import uuid

class MockPaymentState(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

@dataclass(frozen=True)
class PaymentIntent:
    provider_payment_id: str
    checkout_url: str
    state: MockPaymentState

@dataclass(frozen=True)
class ProviderEvent:
    provider_event_id: str
    provider_transaction_id: str
    event_type: str
    amount: str
    currency: str

class PaymentProvider:
    def create_payment_intent(self, *, booking_id: str, amount: str, currency: str) -> PaymentIntent:
        raise NotImplementedError

    def success_event(self, *, provider_payment_id: str, amount: str, currency: str) -> ProviderEvent:
        raise NotImplementedError

    def failure_event(self, *, provider_payment_id: str, amount: str, currency: str) -> ProviderEvent:
        raise NotImplementedError

    def initiate_refund(self, *, payment_id: str, amount: str, currency: str) -> dict:
        raise NotImplementedError

class MockPaymentProvider(PaymentProvider):
    """DEV/STAGING only. Does not contain EduTrust business logic and never processes real money."""

    provider = "MOCK"

    def create_payment_intent(self, *, booking_id: str, amount: str, currency: str) -> PaymentIntent:
        provider_payment_id = f"mock_pay_{uuid.uuid4()}"
        return PaymentIntent(provider_payment_id=provider_payment_id, checkout_url=f"mock://checkout/{provider_payment_id}", state=MockPaymentState.PENDING)

    def success_event(self, *, provider_payment_id: str, amount: str, currency: str) -> ProviderEvent:
        return ProviderEvent(provider_event_id=f"evt_{uuid.uuid4()}", provider_transaction_id=f"tx_{provider_payment_id}", event_type="payment.confirmed", amount=amount, currency=currency)

    def failure_event(self, *, provider_payment_id: str, amount: str, currency: str) -> ProviderEvent:
        return ProviderEvent(provider_event_id=f"evt_{uuid.uuid4()}", provider_transaction_id=f"tx_{provider_payment_id}", event_type="payment.failed", amount=amount, currency=currency)

    def initiate_refund(self, *, payment_id: str, amount: str, currency: str) -> dict:
        return {"provider_refund_id": f"mock_ref_{uuid.uuid4()}", "status": "PROVIDER_PENDING", "payment_id": payment_id, "amount": amount, "currency": currency}
