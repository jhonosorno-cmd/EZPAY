"""Arma lo que reciben los demás roles a partir de un texto ya transcrito (solo desarrollo).

Para cada turno devuelve, en JSON: `transcript` (Contrato B), `intent` y `resolution` (el `context` de ML 2), el
`context` completo con valores SIMULADOS (cotización sin costo, voz no disponible, presupuesto concedido), la
`decision` del motor de ML 2 y el `say` que oiría la persona. Nada se guarda en disco.
"""
import copy
from datetime import datetime, timezone

from decision.context_io import parse_context
from decision.engine import decide
from decision.say_map import say_situation
from voice.amounts import Amount
from voice.config import ASSET, AGENDA_PATH
from voice.contacts import load_agenda, resolve_recipient
from voice.intents import extract_intent
from voice.phrases import Situation, say
from voice.replies import classify_reply
from voice.transcribe import Transcript


def _engine(nombre: str):
    from voice.transcribe import Engine
    return Engine(nombre)


def _decir(situacion: str | None, intent, resolution: dict) -> str | None:
    if situacion is None:
        return None
    s = Situation(situacion)
    nombre = (resolution.get("contact") or {}).get("name")
    opciones = [o["name"] for o in resolution.get("options", [])]
    probar = [{}, {"amount": intent.amount, "name": nombre}, {"name": nombre}, {"names": opciones},
              {"name": opciones[0] if opciones else None}, {"spoken": intent.recipient or ""},
              {"scale": ASSET.asset_scale}]
    for params in probar:
        try:
            return say(s, **params)
        except (ValueError, KeyError, TypeError):
            continue
    return f"(la situación {situacion} necesita parámetros que esta prueba no simula)"


def _salida_del_motor(contexto: dict, intent) -> dict:
    ctx = parse_context(contexto)
    decision = decide(ctx)
    return {"decision": decision.to_dict(), "say": _decir(say_situation(decision, ctx), intent, contexto["resolution"])}


def salidas_del_comando(texto: str, had_speech: bool, engine: str) -> dict:
    transcript = Transcript(text=texto, had_speech=had_speech, engine=_engine(engine)).to_dict()
    intent = extract_intent(texto, ASSET)
    resolution = resolve_recipient(intent.recipient, load_agenda(AGENDA_PATH)).to_dict()
    cotizacion = None
    if intent.amount is not None and resolution["kind"] == "RESOLVED":
        dinero = intent.amount.to_dict()
        cotizacion = {"debitAmount": dinero, "receiveAmount": dinero, "exceedsRemaining": False}
    contexto = {
        "phase": "COMMAND", "intent": intent.to_dict(), "resolution": resolution,
        "voice": {"status": "NOT_AVAILABLE", "score": None}, "enrolled": False, "hasBudgetGrant": True,
        "quote": cotizacion, "pendingPayment": None, "now": datetime.now(timezone.utc).isoformat(),
        "reply": None, "unclearReplies": 0, "pin": {"result": None, "sessionFailures": 0, "locked": False},
        "transcriptConfidence": None, "intentConfidence": None,
        "config": {"highAmountThreshold": None, "pendingWindowSeconds": 120,
                   "minIntentConfidence": None, "minTranscriptConfidence": None},
    }
    return {"transcript": transcript, "intent": contexto["intent"], "resolution": resolution, "context": contexto,
            **_salida_del_motor(contexto, intent)}


def salidas_de_la_respuesta(contexto_del_comando: dict, texto: str) -> dict:
    """La persona contesta "sí" o "no" a la confirmación: mismo context, fase CONFIRMATION."""
    respuesta = classify_reply(texto)
    contexto = copy.deepcopy(contexto_del_comando)
    contexto.update(phase="CONFIRMATION", reply=respuesta.name)
    amount = contexto["intent"]["amount"]
    intent = extract_intent("", ASSET)
    if amount:
        intent = type("I", (), {"amount": Amount(amount["value"], amount["assetCode"], amount["assetScale"]),
                                "recipient": contexto["intent"]["recipient"]})()
    return {"reply": respuesta.name, "context": contexto, **_salida_del_motor(contexto, intent)}
