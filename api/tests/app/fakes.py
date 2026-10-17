"""Dobles compartidos de las pruebas del orquestador (layout plano, nombres únicos)."""
import tempfile
import weakref
from datetime import datetime, timedelta, timezone

from pin import PinValidator, build_hash_spec
from voice.config import AGENDA_PATH

from app.main import create_app

import node_double

TEST_PIN = "2468"


def test_pin_validator():
    """PinValidator aislado: hash de prueba y estado global en un tmp (NUNCA api/.data)."""
    tmp = tempfile.TemporaryDirectory()
    validator = PinValidator(
        hash_provider=lambda: build_hash_spec(TEST_PIN),
        data_dir=tmp.name,
    )
    weakref.finalize(validator, tmp.cleanup)
    return validator


class FixedClock:
    """Reloj doble: instante fijo en UTC que las pruebas pueden avanzar."""

    def __init__(self, instant: datetime | None = None):
        self.instant = instant or datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.instant

    def advance(self, seconds: float) -> None:
        self.instant = self.instant + timedelta(seconds=seconds)


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
    """App de prueba con Node simulado; active_budget marca el grant de presupuesto ACTIVE.

    Sin pin_validator se inyecta uno de prueba (hash de TEST_PIN) para que los flujos
    con PIN sean deterministas; el PIN real viene del entorno.
    """
    fake = fake_node or node_double.FakeNode()
    overrides.setdefault("pin_validator", test_pin_validator())
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