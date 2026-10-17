"""Traducción dict → Context para el orquestador de Pagos.

Spec: openspec/changes/add-decision-engine/design.md, requisito "El contexto de
entrada" (claves camelCase). `parse_context` es estricto y fail-closed: clave
faltante o desconocida, valor de enum desconocido, `Amount.value` no ASCII-dígitos,
`resolution.kind` UNCLEAR o tipo incorrecto ⇒ InvalidContextError con mensaje
fijo, sin datos del request. `decide_dict` une parse + decide y devuelve el dict
`{"decision", "reason"}` que usa el orquestador.
"""
import re

from .engine import decide
from .models import (
    AgendaOption,
    Amount,
    AmountError,
    Contact,
    Context,
    EngineConfig,
    Intent,
    InvalidContextError,
    parse_instant,
    PendingPayment,
    Phase,
    PinContext,
    PinVerifyResult,
    Quote,
    Reply,
    Resolution,
    ResolutionKind,
    Voice,
    VoiceStatus,
)

_AMT_RE = re.compile(r"^[0-9]+$")

_AMOUNT_KEYS = {"value", "assetCode", "assetScale"}
_INTENT_KEYS = {"action", "amount", "amountError", "recipient", "status"}
_VOICE_KEYS = {"status", "score"}
_QUOTE_KEYS = {"debitAmount", "receiveAmount", "exceedsRemaining"}
_PENDING_KEYS = {"recipient", "createdAt", "status"}
_PIN_KEYS = {"result", "sessionFailures", "locked"}
_CONFIG_KEYS = {"highAmountThreshold", "pendingWindowSeconds", "minIntentConfidence", "minTranscriptConfidence"}
_CONTACT_KEYS = {"alias", "name", "walletAddress", "previouslyPaid"}
_OPTION_KEYS = {"alias", "name"}
_QUOTE_KEYS = {"debitAmount", "receiveAmount", "exceedsRemaining"}

_CONTEXT_KEYS = {
    "phase", "intent", "resolution", "voice", "enrolled", "hasBudgetGrant", "quote",
    "pendingPayment", "now", "reply", "unclearReplies", "pin", "transcriptConfidence",
    "intentConfidence", "config",
}


def _dict(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("bad shape")
    return value


def _instant_str(value):
    """Valida ISO 8601 (mensaje fail-closed vía InvalidContextError) y conserva el texto."""
    parse_instant(value)
    return value


def _num_or_none(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("not a number")
    return value


def _int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("not an int")
    return value


def _bool(value):
    if not isinstance(value, bool):
        raise ValueError("not a bool")
    return value


def _str(value):
    if not isinstance(value, str):
        raise ValueError("not a str")
    return value


def _amount(value):
    if value is None:
        return None
    amount = _dict(value, _AMOUNT_KEYS)
    code = amount["assetCode"]
    scale = amount["assetScale"]
    if not isinstance(code, str) or isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
        raise ValueError("bad amount")
    if not isinstance(amount["value"], str) or not _AMT_RE.fullmatch(amount["value"]):
        raise ValueError("bad amount value")
    return Amount(amount["value"], code, scale)


def _parse_intent(data):
    _dict(data, _INTENT_KEYS)
    error = data["amountError"]
    if error is not None:
        error = AmountError(error)
    return Intent(
        action=data["action"],
        amount=_amount(data["amount"]),
        amountError=error,
        recipient=None if data["recipient"] is None else _str(data["recipient"]),
        status=data["status"],
    )


def _parse_resolution(data):
    if not isinstance(data, dict) or "kind" not in data:
        raise ValueError("bad resolution")
    if data["kind"] == "UNCLEAR":
        raise ValueError("resolution UNCLEAR never reaches the engine")
    kind = ResolutionKind(data["kind"])
    if kind is ResolutionKind.RESOLVED:
        _dict(data, {"kind", "contact"})
        contact = _dict(data["contact"], _CONTACT_KEYS)
        return Resolution(
            kind=kind,
            contact=Contact(
                alias=_str(contact["alias"]),
                name=_str(contact["name"]),
                walletAddress=_str(contact["walletAddress"]),
                previouslyPaid=_bool(contact["previouslyPaid"]),
            ),
        )
    if kind is ResolutionKind.CHOICE:
        _dict(data, {"kind", "options"})
        options = data["options"]
        if not isinstance(options, list):
            raise ValueError("bad options")
        parsed = []
        for option in options:
            _dict(option, _OPTION_KEYS)
            parsed.append(AgendaOption(alias=_str(option["alias"]), name=_str(option["name"])))
        return Resolution(kind=kind, options=tuple(parsed))
    _dict(data, {"kind"})
    return Resolution(kind=kind)


def _parse_voice(data):
    _dict(data, _VOICE_KEYS)
    status = VoiceStatus(data["status"])
    return Voice(status=status, score=_num_or_none(data["score"]))


def _parse_quote(data):
    if data is None:
        return None
    _dict(data, _QUOTE_KEYS)
    return Quote(
        debitAmount=_amount(data["debitAmount"]),
        receiveAmount=_amount(data["receiveAmount"]),
        exceedsRemaining=_bool(data["exceedsRemaining"]),
    )


def _parse_pending(data):
    if data is None:
        return None
    _dict(data, _PENDING_KEYS)
    return PendingPayment(
        recipient=_str(data["recipient"]),
        createdAt=_instant_str(data["createdAt"]),
        status=data["status"],
    )


def _parse_pin(data):
    _dict(data, _PIN_KEYS)
    result = data["result"]
    if result is not None:
        result = PinVerifyResult(result)
    return PinContext(result=result, sessionFailures=_int(data["sessionFailures"]), locked=_bool(data["locked"]))


def _parse_config(data):
    _dict(data, _CONFIG_KEYS)
    return EngineConfig(
        highAmountThreshold=_amount(data["highAmountThreshold"]),
        pendingWindowSeconds=_int(data["pendingWindowSeconds"]),
        minIntentConfidence=_num_or_none(data["minIntentConfidence"]),
        minTranscriptConfidence=_num_or_none(data["minTranscriptConfidence"]),
    )


def parse_context(data: dict) -> Context:
    """dict con las claves camelCase del design.md -> Context. Fail-closed: todo
    lo que no cumpla el contrato exacto (claves, enums, tipos, montos) levanta
    InvalidContextError con mensaje fijo, sin datos del request."""
    try:
        _dict(data, _CONTEXT_KEYS)
        return Context(
            phase=Phase(data["phase"]),
            intent=_parse_intent(data["intent"]),
            resolution=_parse_resolution(data["resolution"]),
            voice=_parse_voice(data["voice"]),
            enrolled=_bool(data["enrolled"]),
            hasBudgetGrant=_bool(data["hasBudgetGrant"]),
            quote=_parse_quote(data["quote"]),
            pendingPayment=_parse_pending(data["pendingPayment"]),
            now=_instant_str(data["now"]),
            reply=None if data["reply"] is None else Reply(data["reply"]),
            unclearReplies=_int(data["unclearReplies"]),
            pin=_parse_pin(data["pin"]),
            transcriptConfidence=_num_or_none(data["transcriptConfidence"]),
            intentConfidence=_num_or_none(data["intentConfidence"]),
            config=_parse_config(data["config"]),
        )
    except InvalidContextError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise InvalidContextError(InvalidContextError.MESSAGE_PARSE) from None


def decide_dict(data: dict) -> dict:
    """dict del context -> dict {"decision", "reason"} (lo que consume el orquestador)."""
    return decide(parse_context(data)).to_dict()