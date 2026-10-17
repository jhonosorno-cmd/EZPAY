"""Errores del Contrato B: AUDIO_OR_TEXT_REQUIRED, SESSION_NOT_FOUND y el formato del body.
Cada cuerpo de error debe tener {error:{code,message}} (CONV-2)."""
import unittest

from app_doubles import DoubleAppMixin
import contract


class ErrorsTest(DoubleAppMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()

    def assert_contract_error(self, r, code, status):
        self.assertEqual(r.status_code, status)
        body = r.json()
        self.assertEqual(body["error"]["code"], code)
        self.assertTrue(body["error"]["message"])
        self.assertNotIn("error", body.get("message", ""))
        return body

    # --- turns ------------------------------------------------------------
    def test_turn_without_audio_nor_text_is_audio_or_text_required(self):
        r = self.client.post("/api/turns", data={})
        self.assert_contract_error(r, "AUDIO_OR_TEXT_REQUIRED", 400)

    def test_turn_with_both_audio_and_text_is_audio_or_text_required(self):
        r = self.client.post(
            "/api/turns",
            files=[("audio", ("comando.wav", b"RIFF", "audio/wav"))],
            data={"text": "envíale veinte mil", "sessionId": ""},
        )
        self.assert_contract_error(r, "AUDIO_OR_TEXT_REQUIRED", 400)

    def test_verify_pending_without_session_id_is_audio_or_text_required(self):
        r = self.client.post("/api/turns", data={"kind": "verify_pending"})
        self.assert_contract_error(r, "AUDIO_OR_TEXT_REQUIRED", 400)

    def test_verify_pending_with_unknown_session_is_session_not_found(self):
        r = self.client.post("/api/turns", data={"sessionId": "s_nadie", "kind": "verify_pending"})
        self.assert_contract_error(r, "SESSION_NOT_FOUND", 404)

    def test_turn_with_unknown_session_is_session_not_found(self):
        r = self.client.post("/api/turns", data={"sessionId": "s_nadie", "text": "hola"})
        self.assert_contract_error(r, "SESSION_NOT_FOUND", 404)

    def test_expired_session_is_session_not_found(self):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        session = self.app.state.session_store.get(first["sessionId"])
        session.created_at -= 10_000  # backdating: la sesión venció hace rato
        r = self.client.post("/api/turns", data={"sessionId": first["sessionId"], "text": "hola de nuevo"})
        self.assert_contract_error(r, "SESSION_NOT_FOUND", 404)

    def test_malformed_json_body_is_rejected_with_error_shape(self):
        r = self.client.post("/api/budget", content=b"{no-es-json", headers={"content-type": "application/json"})
        self.assert_contract_error(r, "INVALID_REQUEST", 400)

    # --- budget / amounts (CONV-1) ----------------------------------------
    def test_budget_with_decimal_value_is_invalid_amount(self):
        r = self.client.post("/api/budget", json={
            "debitAmount": {"value": "200.50", "assetCode": "COP", "assetScale": 2},
        })
        self.assert_contract_error(r, "INVALID_AMOUNT", 400)

    def test_budget_with_numeric_value_is_invalid_amount(self):
        r = self.client.post("/api/budget", json={
            "debitAmount": {"value": 20000, "assetCode": "COP", "assetScale": 2},
        })
        self.assert_contract_error(r, "INVALID_AMOUNT", 400)

    def test_budget_with_negative_value_is_invalid_amount(self):
        r = self.client.post("/api/budget", json={
            "debitAmount": {"value": "-3", "assetCode": "COP", "assetScale": 2},
        })
        self.assert_contract_error(r, "INVALID_AMOUNT", 400)

    # --- enrollment -------------------------------------------------------
    def test_enrollment_without_consent_is_consent_required(self):
        r = self.client.post("/api/enrollment", files=self.three_audios(), data={"consent": "false"})
        self.assert_contract_error(r, "CONSENT_REQUIRED", 400)

    def test_enrollment_with_fewer_samples_is_samples_required(self):
        r = self.client.post("/api/enrollment", files=self.three_audios(2), data={"consent": "true"})
        self.assert_contract_error(r, "SAMPLES_REQUIRED", 400)

    def three_audios(self, n=3):
        return [("audio", (f"muestra{i}.wav", b"RIFF", "audio/wav")) for i in range(n)]


if __name__ == "__main__":
    unittest.main()
