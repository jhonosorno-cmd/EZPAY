"""Lógica compartida del TurnResponse del Contrato B: forma de la respuesta y guardas.

El orquestador construye cada respuesta con `response`; el guard de dígitos
(4 a 6) se usa fuera de AWAITING_PIN para que nunca lleguen a la extracción
de intención ni a ningún LLM (spec turn-orchestration).
"""
import re

from .states import TurnState

_DIGITS = re.compile(r"^\d{4,6}$")

# Say del esqueleto usados todavía por las rutas /api/grant-callback y /api/turns
# (R5 y R6 los reemplazan por el catálogo de Voz).
SAY_AUTHORIZED = "Autorización recibida. ¿Qué más necesitas?"
SAY_REJECTED = "No autorizaste el envío. No se hizo ningún pago."
SAY_PENDING = "El envío está en camino. No hace falta repetirlo."


def response(
    session_id: str,
    state: TurnState,
    say: str,
    transcript: str | None = None,
    interact_url: str | None = None,
    options: list | None = None,
    payment: dict | None = None,
) -> dict:
    return {
        "sessionId": session_id,
        "state": state.value,
        "say": say,
        "transcript": transcript,
        "interactUrl": interact_url,
        "options": options,
        "payment": payment,
    }


def is_digits(text: str) -> bool:
    return bool(text) and _DIGITS.fullmatch(text) is not None