"""Doble del servicio de Pagos (Contrato A, /v1) para las pruebas del orquestador.

Un httpx.MockTransport con cuerpos de los ejemplos de contract-a.yaml (cada
respuesta se valida contra el contrato). Los escenarios configuran qué responde
cada ruta: errores, secuencias de pago y estados de grant. Las llamadas quedan
registradas para que las pruebas demuestren el orden del flujo.
"""
import json
from datetime import datetime, timedelta, timezone

import httpx

import contract_a

BASE = "http://node.test/v1"
ASSETS = {"asset_code": "COP", "asset_scale": 2}
GRANT_ID = "g_abc123"
QUOTE_ID = "q_123abc"
PAYMENT_ID = "p_789def"
INTERACT_URL = "https://auth.interledger-test.dev/interact/example"

AMOUNT_LIMIT = {"value": "20000000", "assetCode": "COP", "assetScale": 2}
AMOUNT_DEBIT_WITHIN = {"value": "2015000", "assetCode": "COP", "assetScale": 2}
AMOUNT_RECEIVE = {"value": "2000000", "assetCode": "COP", "assetScale": 2}
AMOUNT_DEBIT_EXCESS = {"value": "30150000", "assetCode": "COP", "assetScale": 2}
AMOUNT_RECEIVE_EXCESS = {"value": "30000000", "assetCode": "COP", "assetScale": 2}

GRANT_201 = {"grantId": GRANT_ID, "status": "PENDING", "interactUrl": INTERACT_URL}
GRANT_ACTIVE_200 = {
    "grantId": GRANT_ID,
    "status": "ACTIVE",
    "limit": {"debitAmount": AMOUNT_LIMIT, "interval": "R52/2026-10-17T00:00:00Z/P1W"},
    "spent": {"value": "0", "assetCode": "COP", "assetScale": 2},
    "remaining": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
}
CONTINUE_200 = {
    "grantId": GRANT_ID,
    "status": "ACTIVE",
    "limit": {"debitAmount": AMOUNT_LIMIT, "interval": "R52/2026-10-17T00:00:00Z/P1W"},
    "remaining": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
}


def error(status: int, code: str):
    return (status, {"error": {"code": code, "message": code}})


class FakeNode:
    """Simulador del microservicio Node: rutas del Contrato A con respuestas del contrato."""

    def __init__(self):
        self.requests: list[tuple[str, str, dict, dict]] = []
        self.time = 0.0
        # escenarios (se sobreescriben por prueba)
        self.grant_response = (201, GRANT_201)
        self.continue_response = (200, CONTINUE_200)
        self.grant_get_response = (200, GRANT_ACTIVE_200)
        self.quote_response = (201, {
            "quoteId": QUOTE_ID,
            "debitAmount": AMOUNT_DEBIT_WITHIN,
            "receiveAmount": AMOUNT_RECEIVE,
            "expiresAt": "2026-10-17T12:05:00Z",
            "exceedsRemaining": False,
        })
        self.payment_responses: list[tuple[int, dict]] | None = None
        self.payment_index = 0
        self.payment_poll_script: list[str] = ["COMPLETED"]  # estados que devuelve GET /payments
        self.payment_poll_index = 0
        self.cancel_response = (204, None)

    # ------------------------------------------------------------------ helpers
    def clock_value(self) -> float:
        return self.time

    def advance(self, seconds: float = 1.0) -> None:
        self.time += seconds

    def now_utc(self) -> datetime:
        return datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=self.time)

    def payments_client(self, **overrides):
        from payments_client import PaymentsClient

        kwargs = {
            "node_base_url": BASE,
            "asset_code": ASSETS["asset_code"],
            "asset_scale": ASSETS["asset_scale"],
            "http": httpx.Client(transport=httpx.MockTransport(self.handle)),
            "sleep": lambda seconds: None,
            "clock": self.clock_value,
        }
        kwargs.update(overrides)
        return PaymentsClient(**kwargs)

    def calls(self, method: str, path_prefix: str | None = None):
        out = []
        for entry in self.requests:
            if entry[0] != method:
                continue
            if path_prefix is not None and not entry[1].startswith(path_prefix):
                continue
            out.append(entry)
        return out

    def last_body(self) -> dict:
        return self.requests[-1][2]

    def last_header(self, name: str) -> str | None:
        return self.requests[-1][3].get(name)

    # ------------------------------------------------------------------ handler
    def _respond(self, path: str, method: str, status: int, body) -> httpx.Response:
        contract_a.validate_response(path, method, status, body)
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.advance()
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.method, request.url.path, body, dict(request.headers)))
        path, method = request.url.path, request.method
        if path == "/v1/health" and method == "GET":
            return self._respond(path, method, 200, {"ok": True})
        if path == "/v1/grants" and method == "POST":
            status, payload = self.grant_response
            return self._respond(path, method, status, payload)
        if path.endswith("/continue") and method == "POST":
            status, payload = self.continue_response
            return self._respond(path, method, status, payload)
        if path.startswith("/v1/grants/") and method == "GET":
            status, payload = self.grant_get_response
            return self._respond(path, method, status, payload)
        if path.startswith("/v1/grants/") and method == "DELETE":
            status, payload = self.cancel_response
            return self._respond(path, method, status, payload)
        if path == "/v1/quotes" and method == "POST":
            status, payload = self.quote_response
            return self._respond(path, method, status, payload)
        if path == "/v1/payments" and method == "POST":
            if self.payment_responses is not None:
                response = self.payment_responses[min(self.payment_index, len(self.payment_responses) - 1)]
                self.payment_index += 1
                return self._respond(path, method, response[0], response[1])
            return self._respond(path, method, 201, {
                "paymentId": PAYMENT_ID,
                "status": "PROCESSING",
                "debitAmount": AMOUNT_DEBIT_WITHIN,
                "sentAmount": {"value": "0", "assetCode": "COP", "assetScale": 2},
            })
        if path.startswith("/v1/payments/") and method == "GET":
            status = self.payment_poll_script[min(self.payment_poll_index, len(self.payment_poll_script) - 1)]
            self.payment_poll_index += 1
            sent = AMOUNT_RECEIVE if status == "COMPLETED" else {"value": "0", "assetCode": "COP", "assetScale": 2}
            return self._respond(path, method, 200, {"paymentId": PAYMENT_ID, "status": status, "sentAmount": sent})
        raise AssertionError(f"ruta inesperada en el doble de Node: {method} {path}")
