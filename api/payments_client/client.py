"""HTTP client for the Node payments service (Contract A, /v1, port 4000).

One method per contract operation. The client never invents idempotency keys,
never turns an uncertain result into a failure, and never decides by the error
message: only by `error.code` (CONV-2). Amounts keep `value` as a digit-only
string (CONV-1) and their currency/scale are read from the environment.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

DEFAULT_NODE_BASE_URL = "http://localhost:4000/v1"
RETRY_WAIT_SECONDS = (0.5, 1.0)
RETRY_BUDGET_SECONDS = 15.0
MAX_PAYMENT_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 10.0

# (status, code) of POST /payments answers that mean "the result is uncertain or
# the first attempt is still running": retry with the same key, never a new one.
_RETRYABLE_PAYMENTS = {
    (502, "UPSTREAM_ERROR"),
    (500, "INTERNAL_ERROR"),
    (409, "PAYMENT_IN_PROGRESS"),
}

_DIGIT_VALUE = re.compile(r"\d+\Z")


class PaymentsClientConfigError(ValueError):
    """The client cannot start: required environment configuration is missing or invalid."""


class PaymentsError(Exception):
    """A business error answered with the contract shape; decide by `code`, never by `message`."""

    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(f"{code} ({status}): {message}")
        self.status = status
        self.code = code
        self.message = message


class UpstreamUnavailable(Exception):
    """Node is unreachable or answered outside the contract; this is never a business error."""


@dataclass(frozen=True)
class PaymentPending:
    """The payment is not confirmed yet; this never means the payment failed."""

    payment_id: Optional[str]


def _digit_string(value: object) -> str:
    if not isinstance(value, str) or not _DIGIT_VALUE.fullmatch(value):
        raise ValueError(f"amount value must be a digit-only string, got {value!r}")
    return value


class PaymentsClient:
    """Talks to the Node payments service. Knows only grant ids: secrets stay in Node."""

    def __init__(
        self,
        *,
        node_base_url: Optional[str] = None,
        asset_code: Optional[str] = None,
        asset_scale: Optional[int] = None,
        http: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        base = node_base_url if node_base_url is not None else os.environ.get("NODE_BASE_URL")
        self._base = (base or DEFAULT_NODE_BASE_URL).rstrip("/")
        code = asset_code if asset_code is not None else os.environ.get("ASSET_CODE")
        if not code:
            raise PaymentsClientConfigError("ASSET_CODE is required in the environment to build amounts")
        scale_raw = asset_scale if asset_scale is not None else os.environ.get("ASSET_SCALE")
        try:
            scale = int(scale_raw)
        except (TypeError, ValueError):
            raise PaymentsClientConfigError("ASSET_SCALE must be an integer in the environment") from None
        if scale < 0:
            raise PaymentsClientConfigError("ASSET_SCALE must be zero or greater in the environment")
        self._asset_code = code
        self._asset_scale = scale
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=10.0)
        self._sleep = sleep
        self._clock = clock
        self._log = logger or logging.getLogger("payments_client")

    @property
    def base_url(self) -> str:
        return self._base

    # ------------------------------------------------------------- operations
    def health(self, request_id: Optional[str] = None) -> dict:
        status, body = self._request("health", "GET", f"{self._base}/health", request_id=request_id)
        return self._ok(status, body)

    def create_grant(
        self,
        user_id: str,
        wallet_address: str,
        finish_uri: str,
        debit_value: str,
        interval: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> dict:
        limit: dict = {"debitAmount": self._amount(debit_value)}
        if interval is not None:
            limit["interval"] = interval
        payload = {
            "userId": user_id,
            "walletAddress": wallet_address,
            "finishUri": finish_uri,
            "limit": limit,
        }
        status, body = self._request(
            "create_grant", "POST", f"{self._base}/grants", json_body=payload, request_id=request_id
        )
        return self._ok(status, body)

    def continue_grant(self, grant_id: str, interact_ref: str, hash_value: str, request_id: Optional[str] = None) -> dict:
        payload = {"interactRef": interact_ref, "hash": hash_value}
        status, body = self._request(
            "continue_grant",
            "POST",
            f"{self._base}/grants/{grant_id}/continue",
            json_body=payload,
            request_id=request_id,
        )
        return self._ok(status, body)

    def get_grant(self, grant_id: str, request_id: Optional[str] = None) -> dict:
        status, body = self._request("get_grant", "GET", f"{self._base}/grants/{grant_id}", request_id=request_id)
        return self._ok(status, body)

    def cancel_grant(self, grant_id: str, request_id: Optional[str] = None) -> None:
        status, _ = self._request("cancel_grant", "DELETE", f"{self._base}/grants/{grant_id}", request_id=request_id)
        if status != 204:
            raise self._error(status, _)

    def create_quote(self, grant_id: str, receiver: str, receive_value: str, request_id: Optional[str] = None) -> dict:
        payload = {"grantId": grant_id, "receiver": receiver, "receiveAmount": self._amount(receive_value)}
        status, body = self._request(
            "create_quote", "POST", f"{self._base}/quotes", json_body=payload, request_id=request_id
        )
        return self._ok(status, body)

    def create_payment(self, quote_id: str, idempotency_key: str, request_id: Optional[str] = None):
        """Pays a quote. The key belongs to the caller (one per quote): retries reuse it.

        Returns the 201 body, or `PaymentPending` when the retries are exhausted:
        an uncertain result is never turned into a rejection. Business 4xx codes
        raise `PaymentsError` without retries; the orchestrator decides.
        """
        deadline = self._clock() + RETRY_BUDGET_SECONDS
        for attempt in range(1, MAX_PAYMENT_ATTEMPTS + 1):
            try:
                status, body = self._request(
                    "create_payment",
                    "POST",
                    f"{self._base}/payments",
                    json_body={"quoteId": quote_id},
                    headers={"Idempotency-Key": idempotency_key},
                    request_id=request_id,
                )
            except UpstreamUnavailable:
                if attempt == MAX_PAYMENT_ATTEMPTS:
                    return PaymentPending(payment_id=None)
                self._sleep(RETRY_WAIT_SECONDS[attempt - 1])
                if self._clock() >= deadline:
                    return PaymentPending(payment_id=None)
                continue
            if status == 201:
                return body
            if (status, self._code_of(body)) in _RETRYABLE_PAYMENTS:
                if attempt == MAX_PAYMENT_ATTEMPTS:
                    return PaymentPending(payment_id=None)
                self._sleep(RETRY_WAIT_SECONDS[attempt - 1])
                if self._clock() >= deadline:
                    return PaymentPending(payment_id=None)
                continue
            raise self._error(status, body)
        return PaymentPending(payment_id=None)

    def get_payment(self, payment_id: str, request_id: Optional[str] = None) -> dict:
        status, body = self._request("get_payment", "GET", f"{self._base}/payments/{payment_id}", request_id=request_id)
        return self._ok(status, body)

    def wait_for_payment(
        self,
        payment_id: str,
        interval: float = POLL_INTERVAL_SECONDS,
        timeout: float = POLL_TIMEOUT_SECONDS,
        request_id: Optional[str] = None,
    ):
        """Polls GET /payments/{id} until COMPLETED or FAILED; PAYMENT_PENDING on timeout.

        Never declares a failure by itself: FAILED comes only from Open Payments.
        """
        deadline = self._clock() + timeout
        while True:
            body = self.get_payment(payment_id, request_id=request_id)
            if body.get("status") in ("COMPLETED", "FAILED"):
                return body
            remaining = deadline - self._clock()
            if remaining <= 0:
                return PaymentPending(payment_id=payment_id)
            self._sleep(min(interval, remaining))

    # --------------------------------------------------------------- internals
    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    @staticmethod
    def _ok(status: int, body: object) -> dict:
        if status >= 400:
            raise PaymentsError(status, PaymentsClient._code_of(body), PaymentsClient._message_of(body))
        return body

    def _amount(self, value: str) -> dict:
        return {
            "value": _digit_string(value),
            "assetCode": self._asset_code,
            "assetScale": self._asset_scale,
        }

    @staticmethod
    def _code_of(body: object) -> str:
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            code = body["error"].get("code")
            if isinstance(code, str):
                return code
        return ""

    def _error(self, status: int, body: object) -> PaymentsError:
        return PaymentsError(status, self._code_of(body), self._message_of(body))

    @staticmethod
    def _message_of(body: object) -> str:
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            message = body["error"].get("message")
            if isinstance(message, str):
                return message
        return ""

    def _request(
        self,
        operation: str,
        method: str,
        url: str,
        *,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
        request_id: Optional[str] = None,
    ):
        request_headers = dict(headers or {})
        if request_id:
            request_headers["X-Request-Id"] = request_id
        try:
            response = self._http.request(method, url, json=json_body, headers=request_headers)
        except httpx.HTTPError:
            self._log_line(operation, "unavailable", "", request_id)
            raise UpstreamUnavailable(operation) from None
        if response.status_code == 204:
            self._log_line(operation, response.status_code, "", request_id)
            return response.status_code, None
        if "application/json" not in response.headers.get("content-type", ""):
            self._log_line(operation, "unavailable", "", request_id)
            raise UpstreamUnavailable(operation)
        try:
            body = response.json()
        except ValueError:
            self._log_line(operation, "unavailable", "", request_id)
            raise UpstreamUnavailable(operation) from None
        code = self._code_of(body) if response.status_code >= 400 else ""
        if response.status_code >= 400 and not code:
            self._log_line(operation, "unavailable", "", request_id)
            raise UpstreamUnavailable(operation)
        self._log_line(operation, response.status_code, code, request_id)
        return response.status_code, body

    def _log_line(self, operation: str, status: object, code: str, request_id: Optional[str]) -> None:
        parts = [f"op={operation}", f"status={status}"]
        if code:
            parts.append(f"code={code}")
        if request_id:
            parts.append(f"requestId={request_id}")
        self._log.info(" ".join(parts))