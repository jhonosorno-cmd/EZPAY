"""Client for the Node payments service (Contract A, /v1) — capability payments-client.

Client-side rules of `openspec/changes/add-payments-client`: an Idempotency-Key
per payment intent, retries with the same key on uncertain results, decisions by
`error.code`, payment polling with PAYMENT_PENDING, and amounts whose currency
and scale come from the environment only (ASSET_CODE, ASSET_SCALE).
"""
from .client import (
    PaymentPending,
    PaymentsClient,
    PaymentsClientConfigError,
    PaymentsError,
    UpstreamUnavailable,
)
from .intervals import one_off_interval

__all__ = [
    "PaymentPending",
    "PaymentsClient",
    "PaymentsClientConfigError",
    "PaymentsError",
    "UpstreamUnavailable",
    "one_off_interval",
]