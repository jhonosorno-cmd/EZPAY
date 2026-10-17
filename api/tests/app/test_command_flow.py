"""R3 — turno de comando por texto y por audio: intención, agenda, verificación de voz,
quote antes del motor, tabla de transiciones y `say` del catálogo de Voz. Un escenario
del spec turn-orchestration por prueba."""
import unittest

from fastapi.testclient import TestClient

import contract
import fakes
import node_double


def text_turn(client, text, session_id=None, headers=None):
    data = {"text": text}
    if session_id:
        data["sessionId"] = session_id
    return client.post("/api/turns", data=data, headers=headers or {})


def audio_turn(client, session_id=None, body=b"RIFF-DE-PRUEBA"):
    data = {"sessionId": session_id} if session_id else {}
    return client.post(
        "/api/turns",
        files=[("audio", ("comando.wav", body, "audio/wav"))],
        data=data,
    )


class CommandFlowTest(unittest.TestCase):
    def setUp(self):
        self.log: list = []
        self.app, self.node = fakes.make_app(
            transcriber=fakes.RecordingTranscriber("envíale veinte mil a mi hija", log=self.log),
            verifier=fakes.RecordingVerifier(log=self.log),
        )
        self.client = TestClient(self.app)

    def test_full_payment_command_order_voice_quote_engine_transition(self):
        """Spec «Turno de pago completo»: intención, agenda, verificación, quote, motor, transición."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        r = audio_turn(self.client)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "AWAITING_CONFIRMATION")
        # el orden del spec: transcribir -> verificar -> quote -> (motor puro) -> transición
        self.assertEqual(self.log, ["transcribe", "verify"])
        self.assertEqual(len(self.node.calls("POST", "/v1/quotes")), 1)
        # sin X-Request-Id del frontend, Python genera el suyo y lo propaga igual (CONV-3)
        self.assertTrue(self.node.last_header("X-Request-Id"))
        # say del catálogo: receiveAmount y destinatario, nunca costo ni débito
        self.assertEqual(body["say"], "¿Le envío 20.000 pesos a Laura hija?")

    def test_same_context_produces_the_same_state(self):
        """Spec «Mapeo determinístico»: mismo context -> mismo TurnState."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        first = text_turn(self.client, "envíale veinte mil a mi hija").json()
        second = text_turn(self.client, "envíale veinte mil a mi hija").json()
        self.assertEqual(first["state"], second["state"])
        self.assertEqual(first["say"], second["say"])

    def test_command_without_budget_grant_skips_the_quote(self):
        """Spec «Sin grant de presupuesto»: quote null y REQUIRE_AUTH sin llamada de quote."""
        r = text_turn(self.client, "envíale veinte mil a mi hija")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "AWAITING_AUTHORIZATION")
        self.assertTrue(body["interactUrl"])
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])
        self.assertEqual(len(self.node.calls("POST", "/v1/grants")), 1)
        # el grant de presupuesto se pide con el monto del comando y sin interval (tope total)
        grant_body = self.node.calls("POST", "/v1/grants")[0][2]
        self.assertEqual(grant_body["limit"]["debitAmount"]["value"], "2000000")
        self.assertNotIn("interval", grant_body["limit"])

    def test_text_command_without_budget_grant_asks_pin_after_authorization_state(self):
        """Un comando por texto entra NOT_AVAILABLE, pero sin presupuesto gana REQUIRE_AUTH."""
        r = text_turn(self.client, "envíale veinte mil a mi hija")
        self.assertEqual(r.json()["state"], "AWAITING_AUTHORIZATION")

    def test_unclear_intent_reasks_with_the_catalog_template(self):
        """Spec «Intención confusa»: REASK -> AWAITING_COMMAND y no paga."""
        r = text_turn(self.client, "hola")
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.assertEqual(body["say"], "No te entendí. ¿Me lo repites?")
        self.assertEqual(body["transcript"], "hola")
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])

    def test_recipient_outside_the_agenda_reasks(self):
        """Spec «destinatario fuera de la agenda»: REASK con el nombre dicho."""
        r = text_turn(self.client, "envíale veinte mil a Pedro")
        body = r.json()
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        # el destinatario dicho se ecoa tal como lo entendió el pipeline (normalizado)
        self.assertEqual(body["say"], "No encontré a pedro en tu agenda.")
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])

    def test_ambiguous_recipient_asks_for_the_choice(self):
        """Spec «Destinatario ambiguo»: ASK_RECIPIENT -> AWAITING_RECIPIENT_CHOICE con options."""
        r = text_turn(self.client, "envíale veinte mil a Laura")
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "AWAITING_RECIPIENT_CHOICE")
        self.assertEqual(body["options"], [
            {"alias": "mi-hija", "name": "Laura hija"},
            {"alias": "laura-vecina", "name": "Laura vecina"},
        ])
        self.assertEqual(body["say"], "¿A cuál? Laura hija o Laura vecina.")
        self.assertIsNone(body["interactUrl"])
        # sin wallet resuelta no se puede cotizar
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])

    def test_text_command_with_budget_grant_asks_pin(self):
        """Spec «Texto pide PIN»: verificación NOT_AVAILABLE -> ASK_PIN."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        r = text_turn(self.client, "envíale veinte mil a mi hija")
        body = r.json()
        self.assertEqual(body["state"], "AWAITING_PIN")
        self.assertEqual(body["say"], "Por seguridad, escribe tu PIN en el teclado.")
        self.assertEqual(len(self.node.calls("POST", "/v1/quotes")), 1)

    def test_voice_below_threshold_asks_pin(self):
        """Spec «Voz dudosa»: verificación por debajo del umbral -> ASK_PIN -> AWAITING_PIN."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        app, _ = fakes.make_app(
            fake_node=self.node,
            transcriber=fakes.RecordingTranscriber("envíale veinte mil a mi hija", log=self.log),
            verifier=fakes.RecordingVerifier(status="BELOW_THRESHOLD", score=0.3, log=self.log),
            active_budget=True,
        )
        r = TestClient(app).post("/api/turns", files=[("audio", ("c.wav", b"RIFF", "audio/wav"))])
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "AWAITING_PIN")

    def test_voice_command_without_enrollment_asks_pin(self):
        """Spec «Comando por voz sin enrolamiento»: enrolled false -> ASK_PIN."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        app, _ = fakes.make_app(
            fake_node=self.node,
            transcriber=fakes.RecordingTranscriber("envíale veinte mil a mi hija", log=self.log),
            verifier=fakes.RecordingVerifier(enrolled=False, status="NOT_AVAILABLE", score=None, log=self.log),
            active_budget=True,
        )
        r = TestClient(app).post("/api/turns", files=[("audio", ("c.wav", b"RIFF", "audio/wav"))])
        self.assertEqual(r.json()["state"], "AWAITING_PIN")

    def test_cancel_intent_rejects_without_paying(self):
        """«Cancela» -> REJECT -> REJECTED con la plantilla del catálogo."""
        r = text_turn(self.client, "cancela")
        body = r.json()
        contract.validate_response("POST", "/api/turns", 200, body)
        self.assertEqual(body["state"], "REJECTED")
        self.assertEqual(body["say"], "Listo, cancelé el envío.")

    def test_too_many_decimals_reasks_with_the_scale(self):
        """AMOUNT_ERROR TOO_MANY_DECIMALS -> REASK con la escala de la configuración."""
        r = text_turn(self.client, "envíale 10,505 a mi hija")
        body = r.json()
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.assertEqual(body["say"], "Solo puedo enviar montos con hasta 2 decimales. ¿Me lo dices otra vez?")

    def test_digits_outside_pin_never_reach_the_intent(self):
        """Spec «Sesión perdida con dígitos»: dígitos fuera de AWAITING_PIN -> REASK."""
        r = text_turn(self.client, "1234")
        body = r.json()
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])

    def test_request_id_is_propagated_to_node(self):
        """CONV-3: el X-Request-Id del turno llega al Contrato A."""
        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"
        text_turn(self.client, "envíale veinte mil a mi hija", headers={"X-Request-Id": "turno-abc"})
        self.assertEqual(self.node.last_header("X-Request-Id"), "turno-abc")

    def test_node_unreachable_answers_internal_error(self):
        """Contrato B /api/turns no define 502: Node inalcanzable -> 500 INTERNAL_ERROR (fail-closed)."""
        import httpx

        self.app.state.orchestrator.budget_grant_id = node_double.GRANT_ID
        self.app.state.orchestrator.budget_status = "ACTIVE"

        original = self.node.handle

        def broken(request):
            raise httpx.ConnectError("connection refused")

        self.node.handle = broken
        try:
            r = text_turn(self.client, "envíale veinte mil a mi hija")
        finally:
            self.node.handle = original
        body = r.json()
        self.assertEqual(r.status_code, 500)
        contract.validate_response("POST", "/api/turns", 500, body)
        self.assertEqual(body["error"]["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()