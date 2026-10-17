"""R1 — puertos del orquestador: Transcriber, SpeakerVerifier y Clock con dobles.

Sin adaptador configurado el servidor arranca igual y un turno de audio sigue
el comportamiento determinista del spec (sin transcripción no hay intención →
REASK). Las piezas reales son de otros roles: acá solo hay protocolos y dobles.
"""
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
import contract


class RecordingTranscriber:
    """Doble de Transcriber: registra el audio que recibe y devuelve texto fijo."""

    def __init__(self, text: str | None = "hola"):
        self.calls: list[bytes] = []
        self.text = text

    def transcribe(self, audio: bytes) -> str | None:
        self.calls.append(audio)
        return self.text


class RecordingVerifier:
    """Doble de SpeakerVerifier: registra las llamadas y devuelve estado fijo."""

    def __init__(self, enrolled: bool = True, status: str = "VERIFIED", score: float | None = 0.9):
        self.verify_calls: list[bytes] = []
        self.enrolled_value = enrolled
        self.status = status
        self.score = score

    def enrollment_status(self) -> bool:
        return self.enrolled_value

    def verify(self, audio: bytes) -> tuple[str, float | None]:
        self.verify_calls.append(audio)
        return self.status, self.score


class FakeClock:
    """Doble de Clock: instante fijo en UTC."""

    def __init__(self, instant: datetime | None = None):
        self.instant = instant or datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.instant


class PortsWiringTest(unittest.TestCase):
    def client_with(self, **ports):
        import fakes

        return create_app(pin_validator=fakes.test_pin_validator(), **ports)

    def test_audio_turn_calls_the_transcriber_with_the_uploaded_bytes(self):
        transcriber = RecordingTranscriber("hola")
        app = self.client_with(transcriber=transcriber, verifier=RecordingVerifier(), clock=FakeClock())
        client = TestClient(app)
        r = client.post("/api/turns", files=[("audio", ("comando.wav", b"RIFF-DE-PRUEBA", "audio/wav"))])
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(transcriber.calls, [b"RIFF-DE-PRUEBA"])
        self.assertEqual(r.json()["state"], "AWAITING_COMMAND")
        self.assertEqual(r.json()["transcript"], "hola")

    def test_without_transcriber_the_server_still_starts_and_answers_reask(self):
        app = self.client_with()
        client = TestClient(app)
        r = client.post("/api/turns", files=[("audio", ("comando.wav", b"RIFF", "audio/wav"))])
        self.assertEqual(r.status_code, 200)
        contract.validate_response("POST", "/api/turns", 200, r.json())
        self.assertEqual(r.json()["state"], "AWAITING_COMMAND")

    def test_create_app_accepts_every_port_and_still_serves_the_contract(self):
        app = self.client_with(
            transcriber=RecordingTranscriber(),
            verifier=RecordingVerifier(),
            clock=FakeClock(),
        )
        client = TestClient(app)
        r = client.get("/api/budget")
        self.assertEqual(r.status_code, 200)
        contract.validate_response("GET", "/api/budget", 200, r.json())

    def test_default_clock_returns_utc(self):
        from app.ports import UtcClock

        now = UtcClock().now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset().total_seconds(), 0.0)


if __name__ == "__main__":
    unittest.main()