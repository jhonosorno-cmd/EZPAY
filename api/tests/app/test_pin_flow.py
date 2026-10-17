"""R4 — PIN: validación local con api/pin, intentos y bloqueo, audio descartado.

El PIN nunca sale de Python: no va a Node (Contrato A), ni a los logs, ni queda
en la sesión, ni en las excepciones. El hash viene del entorno (en pruebas, de
build_hash_spec con un PIN inventado).
"""
import json
import logging
import unittest

from fastapi.testclient import TestClient

import contract
import fakes
import node_double

PIN_DE_PRUEBA = fakes.TEST_PIN
PIN_INCORRECTO = "1357"


def pin_validator():
    return fakes.test_pin_validator()


class PinFlowTest(unittest.TestCase):
    def setUp(self):
        self.app, self.node = fakes.make_app(active_budget=True, pin_validator=pin_validator())
        self.client = TestClient(self.app)

    def reach_pin(self, text="envíale veinte mil a mi hija"):
        r = self.client.post("/api/turns", data={"text": text}).json()
        self.assertEqual(r["state"], "AWAITING_PIN")
        return r["sessionId"]

    def test_first_wrong_pin_asks_again_with_two_attempts_left(self):
        session_id = self.reach_pin()
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_INCORRECTO}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_PIN")
        self.assertEqual(r["say"], "PIN incorrecto. Te quedan 2 intentos.")
        self.assertIsNone(r["transcript"])

    def test_wrong_pin_attempts_exhausted_rejects_without_paying(self):
        session_id = self.reach_pin()
        for _ in range(2):
            self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_INCORRECTO})
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_INCORRECTO}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "REJECTED")
        self.assertEqual(r["say"], "No pude verificarte. No envié nada.")
        self.assertEqual(self.node.calls("POST", "/v1/payments"), [])

    def test_correct_pin_continues_to_confirmation(self):
        session_id = self.reach_pin()
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_DE_PRUEBA}).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(r["say"], "¿Le envío 20.000 pesos a Laura hija?")
        self.assertIsNone(r["transcript"])

    def test_short_pin_is_invalid_format_without_consuming_attempts(self):
        session_id = self.reach_pin()
        for _ in range(2):
            r = self.client.post("/api/turns", data={"sessionId": session_id, "text": "12"}).json()
            self.assertEqual(r["state"], "AWAITING_PIN")
            self.assertEqual(r["say"], "El PIN tiene entre 4 y 6 números. Escríbelo otra vez.")
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_INCORRECTO}).json()
        self.assertEqual(r["say"], "PIN incorrecto. Te quedan 2 intentos.")

    def test_global_lock_rejects(self):
        validator = pin_validator()
        # 5 fallos globales necesitan sesiones distintas: a los 3 fallos una sesión
        # deja de validar (defensa en profundidad del componente de PIN)
        for i in range(5):
            validator.verify("9999", f"otra-sesion-{i}")
        app, _ = fakes.make_app(active_budget=True, pin_validator=validator)
        client = TestClient(app)
        r = client.post("/api/turns", data={"text": "envíale veinte mil a mi hija"}).json()
        session_id = r["sessionId"]
        r = client.post("/api/turns", data={"sessionId": session_id, "text": PIN_DE_PRUEBA}).json()
        self.assertEqual(r["state"], "REJECTED")
        self.assertEqual(r["say"], "Por seguridad, el PIN está bloqueado. No envié nada.")

    def test_audio_in_awaiting_pin_is_discarded_without_transcription(self):
        transcriber = fakes.RecordingTranscriber("hola")
        verifier = fakes.RecordingVerifier()
        app, _ = fakes.make_app(
            active_budget=True,
            pin_validator=pin_validator(),
            transcriber=transcriber,
            verifier=verifier,
        )
        client = TestClient(app)
        first = client.post("/api/turns", data={"text": "envíale veinte mil a mi hija"}).json()
        session_id = first["sessionId"]
        r = client.post(
            "/api/turns",
            files=[("audio", ("audio.wav", b"RIFF", "audio/wav"))],
            data={"sessionId": session_id},
        ).json()
        contract.validate_response("POST", "/api/turns", 200, r)
        self.assertEqual(r["state"], "AWAITING_PIN")
        self.assertIsNone(r["transcript"])
        # el audio no se transcribió ni se envió a verificación
        self.assertEqual(transcriber.calls, [])
        self.assertEqual(verifier.verify_calls, [])

    def test_pin_never_leaves_python(self):
        """El PIN no viaja a Node ni a ningún servicio externo (Contrato A)."""
        session_id = self.reach_pin()
        self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_DE_PRUEBA})
        for method, path, body, headers in self.node.requests:
            self.assertNotIn(PIN_DE_PRUEBA, json.dumps(body), f"el PIN salió en {method} {path}")
            self.assertNotIn(PIN_DE_PRUEBA, json.dumps(headers))

    def test_pin_is_never_in_the_logs(self):
        class Capture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.lines = []

            def emit(self, record):
                self.lines.append(record.getMessage())

        capture = Capture()
        logger = logging.getLogger("api.app")
        logger.addHandler(capture)
        self.addCleanup(logger.removeHandler, capture)

        session_id = self.reach_pin()
        self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_INCORRECTO})
        for line in capture.lines:
            self.assertNotIn(PIN_INCORRECTO, line)

    def test_pin_is_never_in_the_session(self):
        session_id = self.reach_pin()
        self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_DE_PRUEBA})
        session = self.app.state.session_store.get(session_id)
        dump = repr(vars(session))
        self.assertNotIn(PIN_DE_PRUEBA, dump)

    def test_pin_is_never_in_the_response(self):
        session_id = self.reach_pin()
        r = self.client.post("/api/turns", data={"sessionId": session_id, "text": PIN_DE_PRUEBA}).json()
        self.assertNotIn(PIN_DE_PRUEBA, json.dumps(r))


if __name__ == "__main__":
    unittest.main()