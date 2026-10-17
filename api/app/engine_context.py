"""Construcción del `context` del motor (R2) exactamente con la forma de api/decision.

Fuentes de cada campo (spec turn-orchestration):
- phase: la fase del turno (COMMAND, PIN o CONFIRMATION).
- intent: extract_intent de api/voice sobre el texto del turno (transcrito o escrito).
- resolution: resolve_recipient de api/voice contra la agenda.
- voice: el puerto SpeakerVerifier; un comando por texto entra NOT_AVAILABLE (regla de ML 2).
- enrolled: el puerto SpeakerVerifier.
- quote / hasBudgetGrant: el cliente de Node (Contrato A) y el grant de presupuesto de la app.
- pendingPayment: el pago pendiente que lleva la sesión.
- now: el reloj inyectado (el orquestador nunca lee el reloj de pared).
- config: umbrales de ML 2 (None hasta que los defina) y ventana de pago pendiente propuesta por Pagos.
Los montos son {value: dígitos, assetCode, assetScale} con moneda y escala SOLO del entorno (CONV-1).
"""
from __future__ import annotations

from typing import Optional

from voice.amounts import AssetConfig
from voice.contacts import resolve_recipient
from voice.intents import extract_intent

from .config import asset_code, asset_scale


def _asset_config() -> AssetConfig:
    return AssetConfig(asset_code(), asset_scale())


def intent_dict(text: Optional[str]) -> dict:
    return extract_intent(text, _asset_config()).to_dict()


def resolution_dict(intent: dict, agenda) -> dict:
    recipient = intent.get("recipient")
    if agenda is None:
        from voice.config import AGENDA_PATH

        from voice.contacts import load_agenda

        agenda = load_agenda(AGENDA_PATH)
    return resolve_recipient(recipient, agenda).to_dict()


def voice_dict(status: str, score: Optional[float]) -> dict:
    return {"status": status, "score": score}


def pin_dict(pin_result=None) -> dict:
    """Forma de `pin` en el context. `pin_result` es el PinResult del componente."""
    if pin_result is None:
        return {"result": None, "sessionFailures": 0, "locked": False}
    return {
        "result": pin_result.result,
        "sessionFailures": pin_result.sessionFailures,
        "locked": pin_result.locked,
    }


def quote_dict(quote: Optional[dict]) -> Optional[dict]:
    """La quote del cliente (Contrato A) a la forma del motor: solo débito, recibido y exceso."""
    if quote is None:
        return None
    return {
        "debitAmount": quote["debitAmount"],
        "receiveAmount": quote["receiveAmount"],
        "exceedsRemaining": quote["exceedsRemaining"],
    }


def config_dict() -> dict:
    """Umbrales del motor: decisión de ML 2 (None hasta que los publique).

    pendingWindowSeconds: tope de 2 minutos propuesto por Pagos en turn-orchestration
    ("Propuesta de Pagos: tope de 2 minutos; el umbral final lo confirma ML 2").
    """
    return {
        "highAmountThreshold": None,
        "pendingWindowSeconds": 120,
        "minIntentConfidence": None,
        "minTranscriptConfidence": None,
    }


def build_context(
    *,
    phase: str,
    input_text: Optional[str],
    voice_status: str,
    voice_score: Optional[float],
    enrolled: bool,
    has_budget_grant: bool,
    quote: Optional[dict],
    pending_payment: Optional[dict],
    clock,
    agenda=None,
    reply: Optional[str] = None,
    unclear_replies: int = 0,
    pin_result=None,
) -> dict:
    """El dict completo que consume decision.decide_dict; fail-closed por su cuenta."""
    intent = intent_dict(input_text)
    return {
        "phase": phase,
        "intent": intent,
        "resolution": resolution_dict(intent, agenda),
        "voice": voice_dict(voice_status, voice_score),
        "enrolled": enrolled,
        "hasBudgetGrant": has_budget_grant,
        "quote": quote_dict(quote),
        "pendingPayment": pending_payment,
        "now": clock.now().isoformat(),
        "reply": reply,
        "unclearReplies": unclear_replies,
        "pin": pin_dict(pin_result),
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": config_dict(),
    }