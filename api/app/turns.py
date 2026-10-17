"""Lógica mínima y determinista del turno para el esqueleto (sin orquestador ni Node).

Reglas que ya rigen acá (de turn-orchestration y del Contrato B):
- audio en AWAITING_PIN se descarta sin transcribir (transcript null, se pide el teclado).
- un turno de PIN responde con transcript null y el PIN nunca sale de acá (B-7).
- dígitos (4 a 6) fuera de AWAITING_PIN no van a ninguna extracción de intención: REASK.
"""
import re

from .states import TurnState

SAY_REASK = "No te entendí. ¿Puedes repetirlo?"
SAY_PIN = "Escribe tu PIN en el teclado."
SAY_AUTHORIZED = "Autorización recibida. ¿Qué más necesitas?"
SAY_REJECTED = "No autorizaste el envío. No se hizo ningún pago."
SAY_PENDING = "El envío está en camino. No hace falta repetirlo."

_DIGITS = re.compile(r"^\d{4,6}$")


def response(session_id: str, state: TurnState, say: str, transcript: str | None = None) -> dict:
    return {
        "sessionId": session_id,
        "state": state.value,
        "say": say,
        "transcript": transcript,
        "interactUrl": None,
        "options": None,
        "payment": None,
    }


def handle_command(session, has_audio: bool, text: str) -> dict:
    """Turno de comando: el esqueleto no extrae intención; responde REASK determinista."""
    if session.state is TurnState.AWAITING_PIN:
        return response(session.id, TurnState.AWAITING_PIN, SAY_PIN)
    if not has_audio and text and _DIGITS.fullmatch(text):
        return response(session.id, TurnState.AWAITING_COMMAND, SAY_REASK)
    session.state = TurnState.AWAITING_COMMAND
    return response(session.id, TurnState.AWAITING_COMMAND, SAY_REASK, transcript=text or None)


def handle_pin_attempt(session) -> dict:
    """La usuaria escribió el PIN en AWAITING_PIN: sin validación real en esta unidad."""
    return response(session.id, TurnState.AWAITING_PIN, SAY_PIN)
