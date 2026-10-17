"""Puertos del orquestador para piezas que aún no existen en el repo.

El orquestador depende SOLO de estos protocolos: el reconocimiento de voz es de
Voz (ML 1) y la verificación de hablante de Verificación y calidad (ML 2). Sin
adaptador configurado el servidor arranca igual: un turno de audio no puede
transcribirse y el turno responde con el comportamiento determinista del spec
(REASK). Las pruebas usan dobles; aquí no hay implementaciones reales.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

# Estados de la verificación de hablante que acepta el context del motor.
VOICE_VERIFIED = "VERIFIED"
VOICE_BELOW_THRESHOLD = "BELOW_THRESHOLD"
VOICE_NOT_AVAILABLE = "NOT_AVAILABLE"


@runtime_checkable
class Transcriber(Protocol):
    """Voz real (ML 1): bytes de audio -> texto transcrito, o None si no hay habla."""

    def transcribe(self, audio: bytes) -> str | None: ...


@runtime_checkable
class SpeakerVerifier(Protocol):
    """Verificación de hablante real (ML 2): estado de enrolamiento + similitud del audio."""

    def enrollment_status(self) -> bool: ...

    def verify(self, audio: bytes) -> tuple[str, float | None]:
        """Devuelve (VOICE_VERIFIED | VOICE_BELOW_THRESHOLD | VOICE_NOT_AVAILABLE, puntaje)."""


@runtime_checkable
class Clock(Protocol):
    """Reloj inyectable: el orquestador nunca lee el reloj de pared por su cuenta."""

    def now(self) -> datetime: ...


class UtcClock:
    """Reloj por defecto: datetime con zona UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)