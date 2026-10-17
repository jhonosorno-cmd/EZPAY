"""R7 — historial de pagos por destinatario (previouslyPaid, D9), elección de destinatario
(resolve_choice, B-4) y decisión sobre el pago pendiente (el motor decide vía context)."""
import unittest

from fastapi.testclient import TestClient

import contract
import fakes
import node_double


def error_body(status: int, code: str):
    return (status, {"error": {"code": code, "message": code}})


class HistoryChoiceTest(unittest.TestCase):
    def setUp(self):
        self.clock = fakes.FixedClock()
        self.app, self.node = fakes.make_app(
            transcriber=fakes.RecordingTranscriber("envíale veinte mil a carmen"),
            verifier=fakes.RecordingVerifier(),
            clock=self.clock,
            active_budget=True,
        )
        self.client = TestClient(self.app)

    def audio_command(self, transcriber_text="envíale veinte mil a carmen", session_id=None):
        self.app.state.orchestrator.transcriber.text = transcriber_text
        data = {"sessionId": session_id} if session_id else {}
        return self.client.post("/api/turns", files=[("audio", ("c.wav", b"RIFF", "audio/wav"))], data=data).json()

    # --------------------------------------------------------------- historial
    def test_new_recipient_asks_pin_the_first_time(self):
        """Spec «destinatario nuevo»: NEW_RECIPIENT -> ASK_PIN (el umbral es de ML 2)."""
        r = self.audio_command()
        self.assertEqual(r["state"], "AWAITING_PIN")
        self.assertEqual(r["say"], "Es la primera vez que le envías a Carmen. Por seguridad, escribe tu PIN en el teclado.")

    def test_completed_payment_marks_the_recipient_as_previously_paid(self):
        """Spec «Destinatario con pago previo»: tras COMPLETED, el context marca previouslyPaid."""
        r = self.audio_command()
        session_id = r["sessionId"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "2468"}).json()
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.node.payment_poll_script = ["COMPLETED"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "sí"}).json()
        self.assertEqual(r["state"], "COMPLETED")
        # nuevo comando al mismo destinatario con voz verificada: ya no pide PIN por ser nuevo
        r = self.audio_command()
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(r["say"], "¿Le envío 20.000 pesos a Carmen?")

    # ------------------------------------------------------------- elección
    def test_choice_returns_by_alias_text_and_continues(self):
        """B-4: la elección vuelve como text = alias; el flujo del comando continúa."""
        r = self.audio_command("envíale veinte mil a laura")
        self.assertEqual(r["state"], "AWAITING_RECIPIENT_CHOICE")
        session_id = r["sessionId"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "mi-hija"}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(r["say"], "¿Le envío 20.000 pesos a Laura hija?")
        # la quote se pidió con la wallet del contacto elegido (después de la elección)
        quotes = self.node.calls("POST", "/v1/quotes")
        self.assertEqual(quotes[-1][2]["receiver"], "https://ilp.interledger-test.dev/ezpay-placeholder-laura-hija")

    def test_choice_by_voice_resolves_only_against_the_options(self):
        """Spec «Elección de destinatario»: por voz se resuelve SOLO contra las options."""
        r = self.audio_command("envíale veinte mil a laura")
        session_id = r["sessionId"]
        self.app.state.orchestrator.transcriber.text = "laura hija"  # coincide con una option
        r = self.client.post(
            "/api/turns",
            files=[("audio", ("c.wav", b"RIFF", "audio/wav"))],
            data={"sessionId": session_id},
        ).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(r["say"], "¿Le envío 20.000 pesos a Laura hija?")

    def test_voice_choice_outside_the_options_repeats_the_question(self):
        """Spec «Elección por voz fuera de las opciones»: el orquestador repregunta."""
        r = self.audio_command("envíale veinte mil a laura")
        session_id = r["sessionId"]
        self.app.state.orchestrator.transcriber.text = "carmen"
        r = self.client.post(
            "/api/turns",
            files=[("audio", ("c.wav", b"RIFF", "audio/wav"))],
            data={"sessionId": session_id},
        ).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_RECIPIENT_CHOICE")
        self.assertEqual(r["options"], [
            {"alias": "mi-hija", "name": "Laura hija"},
            {"alias": "laura-vecina", "name": "Laura vecina"},
        ])
        self.assertEqual(self.node.calls("POST", "/v1/quotes"), [])

    def test_text_choice_outside_the_options_repeats_the_question(self):
        r = self.audio_command("envíale veinte mil a laura")
        session_id = r["sessionId"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "jose"}).json()
        self.assertEqual(r["state"], "AWAITING_RECIPIENT_CHOICE")

    # ------------------------------------------------------- pago pendiente
    def pending_payment_to_laura(self):
        r = self.audio_command("envíale veinte mil a mi hija")
        session_id = r["sessionId"]
        self.node.payment_poll_script = ["PROCESSING"] * 20  # el polling vence: PAYMENT_PENDING
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "sí"}).json()
        self.assertEqual(r["state"], "PAYMENT_PENDING")
        self.clock.advance(10)  # dentro de la ventana de 120 s
        return session_id

    def test_pending_payment_same_recipient_within_window_blocks(self):
        """Spec «Dentro del tope al mismo destinatario»: el motor bloquea con REASK."""
        session_id = self.pending_payment_to_laura()
        r = self.audio_command("envíale veinte mil a mi hija", session_id=session_id)
        self.assertEqual(r["state"], "AWAITING_COMMAND")
        self.assertEqual(r["say"], "Tu envío anterior a Laura hija aún no termina. Espera un momento.")
        # la quote se pide antes del motor (spec): se creó y el motor la descarta al bloquear
        self.assertEqual(len(self.node.calls("POST", "/v1/quotes")), 2)

    def test_pending_payment_to_another_recipient_flows(self):
        """Spec «Otro destinatario dentro del tope»: el pago nuevo sigue su curso normal."""
        session_id = self.pending_payment_to_laura()
        r = self.audio_command("envíale veinte mil a carmen", session_id=session_id)
        self.assertEqual(r["state"], "AWAITING_PIN")  # Carmen sigue siendo destinataria nueva
        self.assertEqual(r["say"], "Es la primera vez que le envías a Carmen. Por seguridad, escribe tu PIN en el teclado.")

    def test_pending_payment_past_window_continues_with_a_new_quote_and_key(self):
        """Spec «Pasado el tope con un sí claro»: intención nueva, quote nueva y clave nueva."""
        session_id = self.pending_payment_to_laura()
        self.clock.advance(180)  # pasado el tope de 120 s
        r = self.audio_command("envíale veinte mil a mi hija", session_id=session_id)
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(
            r["say"],
            "Tu envío anterior a Laura hija no se pudo confirmar. Si envías otro, Laura hija podría recibir los dos. ¿Le envío 20.000 pesos?",
        )
        self.node.payment_poll_script = ["COMPLETED"]
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "sí"}).json()
        self.assertEqual(r["state"], "COMPLETED")
        quotes = self.node.calls("POST", "/v1/quotes")
        self.assertEqual(len(quotes), 2, "quote nueva tras el tope")
        keys = {call[3]["idempotency-key"] for call in self.node.calls("POST", "/v1/payments")}
        self.assertEqual(len(keys), 1, "la clave nueva es por la quote nueva")

    def test_pending_payment_resolved_in_the_next_command_proceeds(self):
        """Spec «Pendiente que se completa en la próxima interacción»: el comando continúa."""
        session_id = self.pending_payment_to_laura()
        self.node.payment_poll_script = ["COMPLETED"]
        r = self.audio_command("envíale veinte mil a mi hija", session_id=session_id)
        # la verificación observa COMPLETED: el pago anterior ya no bloquea
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")


if __name__ == "__main__":
    unittest.main()
