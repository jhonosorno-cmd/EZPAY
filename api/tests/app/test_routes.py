"""Una prueba por ruta y por estado del turno: cada respuesta se valida contra
openapi/contract-b.yaml (ver contract.py). Estilo unittest como tests/decision y tests/pin."""
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
import contract


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def audio_files(self, n=3):
        return [("audio", (f"muestra{i}.wav", b"RIFF-WAV-DE-PRUEBA", "audio/wav")) for i in range(n)]

    # --- enrollment -------------------------------------------------------
    def test_post_enrollment_validates_against_contract(self):
        r = self.client.post("/api/enrollment", files=self.audio_files(), data={"consent": "true"})
        self.assertEqual(r.status_code, 201)
        contract.validate_response("POST", "/api/enrollment", 201, r.json())

    def test_get_enrollment_validates_against_contract(self):
        r = self.client.get("/api/enrollment")
        self.assertEqual(r.status_code, 200)
        contract.validate_response("GET", "/api/enrollment", 200, r.json())

    # --- budget -----------------------------------------------------------
    def test_post_budget_validates_against_contract(self):
        r = self.client.post("/api/budget", json={
            "debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
            "interval": "R52/2026-10-17T00:00:00Z/P1W",
        })
        self.assertEqual(r.status_code, 201)
        contract.validate_response("POST", "/api/budget", 201, r.json())
        self.assertTrue(r.json()["interactUrl"])

    def test_get_budget_validates_against_contract(self):
        r = self.client.get("/api/budget")
        self.assertEqual(r.status_code, 200)
        contract.validate_response("GET", "/api/budget", 200, r.json())

    def test_get_budget_reflects_the_posted_limit(self):
        amount = {"value": "20000000", "assetCode": "COP", "assetScale": 2}
        self.client.post("/api/budget", json={"debitAmount": amount})
        r = self.client.get("/api/budget")
        self.assertEqual(r.json()["limit"]["debitAmount"], amount)
        self.assertTrue(contract.is_digits_only(r.json()["spent"]["value"]))
        self.assertTrue(contract.is_digits_only(r.json()["remaining"]["value"]))

    # --- grant-callback ---------------------------------------------------
    def test_grant_callback_rejection_validates_and_is_rejected(self):
        r = self.client.post("/api/grant-callback", json={"result": "grant_rejected"})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/grant-callback", 200, r.json())
        self.assertEqual(r.json()["state"], "REJECTED")
        self.assertIsNone(r.json()["transcript"])

    def test_grant_callback_without_interact_ref_is_rejected(self):
        r = self.client.post("/api/grant-callback", json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "REJECTED")

    def test_grant_callback_with_params_continues_to_command(self):
        self.client.post("/api/budget", json={
            "debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2},
        })
        r = self.client.post("/api/grant-callback", json={
            "interactRef": "ref-de-prueba", "hash": "hash-de-prueba",
        })
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/grant-callback", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_COMMAND")

    # --- turns ------------------------------------------------------------
    def test_text_turn_creates_session_and_validates(self):
        r = self.client.post("/api/turns", data={"text": "envíale veinte mil a mi hija"})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        body = r.json()
        self.assertTrue(body["sessionId"])
        self.assertEqual(body["state"], "AWAITING_COMMAND")

    def test_audio_turn_validates_and_answers_reask(self):
        r = self.client.post("/api/turns", files=[("audio", ("comando.wav", b"RIFF", "audio/wav"))])
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_COMMAND")

    def test_turn_with_known_session_reads_state(self):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        r = self.client.post("/api/turns", data={"sessionId": first["sessionId"], "text": "otra cosa"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["sessionId"], first["sessionId"])
        contract.validate_response("POST", "/api/turns", 200, r.json())

    def test_verify_pending_turn_is_valid_and_payment_pending(self):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        r = self.client.post("/api/turns", data={"sessionId": first["sessionId"], "kind": "verify_pending"})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(r.json()["state"], "PAYMENT_PENDING")

    def test_awaiting_pin_turn_with_text_answers_pin_shape(self):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        session = self.app.state.session_store.get(first["sessionId"])
        from app.states import TurnState
        session.state = TurnState.AWAITING_PIN
        r = self.client.post("/api/turns", data={"sessionId": first["sessionId"], "text": "1234"})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_PIN")
        self.assertIsNone(r.json()["transcript"])

    def test_x_request_id_is_echoed(self):
        r = self.client.get("/api/budget", headers={"X-Request-Id": "abc-123"})
        self.assertEqual(r.headers.get("x-request-id"), "abc-123")

    def test_cors_allows_only_the_frontend_origin(self):
        r = self.client.get("/api/budget", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")
        r = self.client.get("/api/budget", headers={"Origin": "https://malicioso.example"})
        self.assertIsNone(r.headers.get("access-control-allow-origin"))

    def test_audio_turn_in_awaiting_pin_is_discarded_without_transcription(self):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        session = self.app.state.session_store.get(first["sessionId"])
        from app.states import TurnState
        session.state = TurnState.AWAITING_PIN
        r = self.client.post("/api/turns", files=[("audio", ("comando.wav", b"RIFF", "audio/wav"))],
                             data={"sessionId": first["sessionId"]})
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_PIN")
        self.assertIsNone(r.json()["transcript"])


if __name__ == "__main__":
    unittest.main()
