"""R5 — presupuesto y callback: POST /api/budget crea el grant con el cliente de Node,
GET /api/budget lee de GET /v1/grants/{id}, y el callback reenvía el interactRef/hash
verbatim a /continue (B-1) buscando la sesión pendiente por grantId/estado."""
import unittest

from fastapi.testclient import TestClient

import contract
import fakes
import node_double


class BudgetCallbackTest(unittest.TestCase):
    def setUp(self):
        self.app, self.node = fakes.make_app()
        self.client = TestClient(self.app)

    def budget_body(self, interval=None):
        body = {"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}}
        if interval:
            body["interval"] = interval
        return body

    def test_post_budget_creates_the_grant_with_the_client(self):
        r = self.client.post("/api/budget", json=self.budget_body(interval="R52/2026-10-17T00:00:00Z/P1W"))
        self.assertEqual(r.status_code, 201)
        contract.validate_response("POST", "/api/budget", 201, r.json())
        self.assertEqual(r.json()["interactUrl"], node_double.INTERACT_URL)
        calls = self.node.calls("POST", "/v1/grants")
        self.assertEqual(len(calls), 1)
        body = calls[0][2]
        self.assertEqual(body["userId"], "demo-user")
        self.assertEqual(body["limit"]["debitAmount"]["value"], "20000000")
        self.assertEqual(body["limit"]["interval"], "R52/2026-10-17T00:00:00Z/P1W")
        self.assertEqual(body["finishUri"], "http://localhost:5173/grant-callback")
        # el grantId queda en la sesión; NUNCA tokens
        session = list(self.app.state.session_store._sessions.values())[0]
        self.assertEqual(session.grant_id, node_double.GRANT_ID)
        self.assertEqual(session.pending_authorization, "budget")

    def test_get_budget_reads_the_grant_from_node(self):
        self.client.post("/api/budget", json=self.budget_body())
        r = self.client.get("/api/budget")
        self.assertEqual(r.status_code, 200)
        contract.validate_response("GET", "/api/budget", 200, r.json())
        body = r.json()
        self.assertEqual(body["status"], "ACTIVE")
        self.assertEqual(body["limit"]["debitAmount"]["value"], "20000000")
        self.assertEqual(body["remaining"]["value"], "20000000")
        self.assertEqual(len(self.node.calls("GET", "/v1/grants/")), 1)

    def test_callback_continues_the_budget_grant_verbatim(self):
        self.client.post("/api/budget", json=self.budget_body())
        r = self.client.post("/api/grant-callback", json={
            "interactRef": " ref tal cual ", "hash": " hash tal cual ",
        })
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/grant-callback", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_COMMAND")
        calls = self.node.calls("POST", "/v1/grants/")
        self.assertEqual(calls[0][2], {"interactRef": " ref tal cual ", "hash": " hash tal cual "})
        # el grant de presupuesto queda ACTIVE para los pagos siguientes
        self.assertEqual(self.app.state.orchestrator.budget_status, "ACTIVE")

    def test_callback_without_interact_ref_is_rejected_without_continue(self):
        """B-1: sin interactRef/hash no se llama a /continue y el turno es REJECTED."""
        self.client.post("/api/budget", json=self.budget_body())
        r = self.client.post("/api/grant-callback", json={"result": "grant_rejected"})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/grant-callback", 200, r.json())
        self.assertEqual(r.json()["state"], "REJECTED")
        self.assertEqual(self.node.calls("POST", "/v1/grants/g_abc123/continue"), [])
        session = list(self.app.state.session_store._sessions.values())[0]
        self.assertEqual(session.state.value, "REJECTED")

    def test_callback_without_pending_session_keeps_unknown_session_id(self):
        """D-2 (aprobado a): sin sesión pendiente, sessionId 'unknown' se mantiene."""
        r = self.client.post("/api/grant-callback", json={"interactRef": "x", "hash": "y"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sessionId"], "unknown")
        self.assertEqual(r.json()["state"], "REJECTED")

    def test_callback_with_node_hash_error_rejects_without_paying(self):
        """INVALID_HASH/GRANT_NOT_PENDING del /continue: fail-closed, REJECTED (D-n 4 del reporte)."""
        self.client.post("/api/budget", json=self.budget_body())
        self.node.continue_response = (400, {"error": {"code": "INVALID_HASH", "message": "El hash no coincide"}})
        r = self.client.post("/api/grant-callback", json={"interactRef": "x", "hash": "y"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "REJECTED")
        self.assertEqual(self.node.calls("POST", "/v1/payments"), [])

    def test_node_unreachable_on_budget_is_upstream_error(self):
        """Contrato B: POST /api/budget tiene 502 UPSTREAM_ERROR."""
        import httpx

        original = self.node.handle

        def broken(request):
            raise httpx.ConnectError("connection refused")

        self.node.handle = broken
        try:
            r = self.client.post("/api/budget", json=self.budget_body())
        finally:
            self.node.handle = original
        self.assertEqual(r.status_code, 502)
        contract.validate_response("POST", "/api/budget", 502, r.json())
        self.assertEqual(r.json()["error"]["code"], "UPSTREAM_ERROR")

    def test_invalid_amount_from_node_is_400_invalid_amount(self):
        self.node.grant_response = (400, {"error": {"code": "INVALID_AMOUNT", "message": "El monto no es válido"}})
        r = self.client.post("/api/budget", json=self.budget_body())
        self.assertEqual(r.status_code, 400)
        contract.validate_response("POST", "/api/budget", 400, r.json())
        self.assertEqual(r.json()["error"]["code"], "INVALID_AMOUNT")


if __name__ == "__main__":
    unittest.main()