"""Privacidad del turno: el PIN nunca sale en logs ni queda en el estado de la sesión,
y los logs del turno nunca incluyen el cuerpo del request (ni audio, ni text, ni PIN)."""
import json
import logging
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.states import TurnState


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class PrivacyTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.capture = LogCapture()
        self.logger = logging.getLogger("api.app")
        self.logger.addHandler(self.capture)
        self.addCleanup(self.logger.removeHandler, self.capture)

    def pin_turn(self, pin):
        first = self.client.post("/api/turns", data={"text": "hola"}).json()
        session = self.app.state.session_store.get(first["sessionId"])
        session.state = TurnState.AWAITING_PIN
        return first, self.client.post("/api/turns", data={"sessionId": first["sessionId"], "text": pin})

    def test_pin_is_never_in_the_logs(self):
        _, r = self.pin_turn("4321")
        self.assertEqual(r.status_code, 200)
        for line in self.capture.lines:
            self.assertNotIn("4321", line)

    def test_pin_is_never_stored_in_the_session(self):
        first, _ = self.pin_turn("4321")
        session = self.app.state.session_store.get(first["sessionId"])
        dump = repr(vars(session))
        self.assertNotIn("4321", dump)

    def test_pin_turn_response_has_null_transcript_and_pin_state(self):
        _, r = self.pin_turn("9999")
        body = r.json()
        self.assertEqual(body["state"], "AWAITING_PIN")
        self.assertIsNone(body["transcript"])

    def test_request_body_is_never_in_the_logs(self):
        self.client.post("/api/turns", data={"text": "PATITO-SECRETO-123"})
        for line in self.capture.lines:
            self.assertNotIn("PATITO-SECRETO-123", line)

    def test_turn_logs_only_whitelisted_keys(self):
        self.client.post("/api/turns", data={"text": "hola"})
        turn_lines = [json.loads(line) for line in self.capture.lines if json.loads(line).get("path") == "/api/turns"]
        self.assertTrue(turn_lines)
        allowed = {"requestId", "method", "path", "status", "durationMs", "state"}
        for parsed in turn_lines:
            self.assertTrue(set(parsed) <= allowed, f"llaves fuera de la lista blanca: {set(parsed) - allowed}")

    def test_every_log_line_is_valid_json(self):
        self.client.post("/api/turns", data={"text": "hola"})
        self.assertTrue(self.capture.lines)
        for line in self.capture.lines:
            json.loads(line)


if __name__ == "__main__":
    unittest.main()
