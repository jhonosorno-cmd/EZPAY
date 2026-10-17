"""Dobles compartidos de las pruebas del orquestador (layout plano, nombres únicos)."""
from datetime import datetime, timezone

from voice.config import AGENDA_PATH

from app.main import create_app

import node_double


class FixedClock:
    """Reloj doble con instante fijo en UTC."""

    def __init__(self, instant: datetime | None = None):
        self.instant = instant or datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.instant


class RecordingTranscriber:
    """Doble de Transcriber: registra el audio y devuelve texto fijo (o None = silencio)."""

    def __init__(self, text: str | None = "hola", log: list | None = None):
        self.calls: list[bytes] = []
        self.text = text
        self.log = log if log is not None else []

    def transcribe(self, audio: bytes) -> str | None:
        self.calls.append(audio)
        self.log.append("transcribe")
        return self.text


class RecordingVerifier:
    """Doble de SpeakerVerifier: registra el audio y devuelve (estado, puntaje) fijos."""

    def __init__(self, enrolled: bool = True, status: str = "VERIFIED", score: float | None = 0.9,
                 log: list | None = None):
        self.verify_calls: list[bytes] = []
        self.enrolled_value = enrolled
        self.status = status
        self.score = score
        self.log = log if log is not None else []

    def enrollment_status(self) -> bool:
        return self.enrolled_value

    def verify(self, audio: bytes) -> tuple[str, float | None]:
        self.verify_calls.append(audio)
        self.log.append("verify")
        return self.status, self.score


def make_app(fake_node: node_double.FakeNode | None = None, *, transcriber=None, verifier=None,
             clock=None, active_budget=False, **overrides):
    """App de prueba con Node simulado; active_budget marca el grant de presupuesto ACTIVE."""
    fake = fake_node or node_double.FakeNode()
    app = create_app(
        payments=fake.payments_client(),
        transcriber=transcriber,
        verifier=verifier,
        clock=clock or FixedClock(),
        agenda_path=AGENDA_PATH,
        **overrides,
    )
    if active_budget:
        orchestrator = app.state.orchestrator
        orchestrator.budget_grant_id = node_double.GRANT_ID
        orchestrator.budget_status = "ACTIVE"
    return app, fake