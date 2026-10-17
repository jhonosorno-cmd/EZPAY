"""Arma lo que reciben los demás roles a partir de un texto ya transcrito (solo desarrollo).

Para cada turno devuelve, en JSON: `transcript` (Contrato B), `intent` y `resolution` (el `context` de ML 2), el
`context` completo con valores SIMULADOS (cotización sin costo, voz no disponible, presupuesto concedido), la
`decision` del motor de ML 2 y el `say` que oiría la persona. Nada se guarda en disco.
"""
import copy
from dataclasses import dataclass
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


@dataclass(frozen=True)
class FraseLibre:
    decir: str
    pesos: int | None       # monto que se espera entender (None = ninguno)
    resolucion: str         # RESOLVED | NOT_FOUND | CHOICE (resolución del destinatario; NOT_FOUND también si no se dijo nombre)
    nota: str = ""


# Frases sugeridas para el modo libre de probar_salidas.py: montos y nombres poco usuales.
FRASES_LIBRES = [
    FraseLibre("Envíale setenta y tres mil cuatrocientos cincuenta pesos a Laura hija", 73450, "RESOLVED"),
    FraseLibre("Envíale trece mil novecientos a Laura hija", 13900, "RESOLVED"),
    FraseLibre("Paga ciento veintiocho mil quinientos a Laura hija", 128500, "RESOLVED"),
    FraseLibre("Mándale doscientos cuarenta y cinco mil a Laura hija", 245000, "RESOLVED"),
    FraseLibre("Envíale un millón trescientos mil a Laura hija", 1300000, "RESOLVED"),
    FraseLibre("Envíale mil quinientos a Laura hija", 1500, "RESOLVED"),
    FraseLibre("Envíale ocho mil a Laura hija", 8000, "RESOLVED"),
    FraseLibre("Envíale cincuenta y cinco mil ochocientos a Laura hija", 55800, "RESOLVED"),
    FraseLibre("Envíale 87.300 a Laura hija", 87300, "RESOLVED", "dilo con cifras"),
    FraseLibre("Envíale 15 mil 500 a Laura hija", 15500, "RESOLVED", "dilo con cifras"),
    FraseLibre("Envíale veinte mil a Sebastián", 20000, "NOT_FOUND", "nombre que no está en la agenda"),
    FraseLibre("Envíale treinta mil a Camila", 30000, "NOT_FOUND", "nombre que no está en la agenda"),
    FraseLibre("Envíale diez mil a Andrés Felipe", 10000, "NOT_FOUND", "nombre compuesto que no está"),
    FraseLibre("Envíale quince mil a mi tía", 15000, "CHOICE", "se parece a \"mi hija\": debe preguntar si quisiste decir Laura hija"),
    FraseLibre("Envíale veinte mil a José", 20000, "RESOLVED", "nombre que sí está"),
    FraseLibre("Envíale veinte mil a Carmen", 20000, "RESOLVED", "nombre que sí está"),
    FraseLibre("Envíale veinte mil a Laura", 20000, "CHOICE", "hay dos Lauras: debe preguntar cuál"),
    FraseLibre("Envíale veinte mil", 20000, "NOT_FOUND", "sin nombre: debe preguntar a quién"),
    FraseLibre("Envíale a Laura hija", None, "RESOLVED", "sin monto: debe preguntar cuánto"),
    FraseLibre("Haz lo que quieras con mi plata", None, "NOT_FOUND", "no es un comando: debe decir que no entendió"),
]
