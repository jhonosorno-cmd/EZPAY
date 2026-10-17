"""Dependencias del orquestador y despacho del turno.

R1: puertos inyectados (Transcriber, SpeakerVerifier, Clock) y el despacho del
turno que mantiene las reglas del esqueleto (dígitos fuera de AWAITING_PIN, PIN
con transcript null). Las rebanadas siguientes reemplazan la lógica mínima por
el orquestador real del spec turn-orchestration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ports import Clock, SpeakerVerifier, Transcriber, UtcClock
from .states import TurnState
from . import turns as skeleton


@dataclass(frozen=True)
class Deps:
    """Todo lo que el turno necesita y que otros roles proveen."""

    transcriber: Transcriber | None
    verifier: SpeakerVerifier | None
    clock: Clock


def default_deps(**overrides) -> Deps:
    values = {
        "transcriber": None,
        "verifier": None,
        "clock": UtcClock(),
    }
    values.update(overrides)
    return Deps(**values)


def handle_turn(session, audio_bytes: bytes | None, text: str, deps: Deps) -> dict:
    """Despacho del turno (R1): reglas del esqueleto con los puertos inyectados."""
    if session.state is TurnState.AWAITING_PIN:
        if audio_bytes is not None:
            return skeleton.response(session.id, TurnState.AWAITING_PIN, skeleton.SAY_PIN)
        return skeleton.handle_pin_attempt(session)
    transcript: str | None = text or None
    if audio_bytes is not None:
        transcript = deps.transcriber.transcribe(audio_bytes) if deps.transcriber else None
    if audio_bytes is not None and not transcript:
        return skeleton.response(session.id, TurnState.AWAITING_COMMAND, skeleton.SAY_REASK, None)
    return skeleton.handle_command(session, has_audio=audio_bytes is not None, text=transcript or "")