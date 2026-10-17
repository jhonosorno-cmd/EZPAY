"""Tipos del motor de decisión.

Espec fuente: openspec/changes/add-decision-engine/specs/decision-engine/spec.md,
requisito "El contexto de entrada" (decidido 2026-10-16 con ML 2, ML 1 y Pagos)
y "Confirmación con desafío de voz" (decidido 2026-10-17, B11).
Los montos se comparan como enteros (CONV-1): Amount.value es un string de solo dígitos.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

_AMOUNT_VALUE_RE = re.compile(r"^[0-9]+$")


class InvalidContextError(ValueError):
    """Contexto inválido armado por el orquestador; el orquestador lo trata como
    error interno (no se paga). Mensajes fijos, sin datos del request."""

    MESSAGE_DEFAULT = "invalid context: malformed or impossible context"
    MESSAGE_PARSE = "invalid context: the context payload does not match the contract"

    def __init__(self, message: str = MESSAGE_DEFAULT) -> None:
        super().__init__(message)


def parse_instant(value) -> datetime:
    """ISO 8601 (con 'Z' o desplazamiento; sin zona = UTC) -> datetime UTC.
    Lanza InvalidContextError con mensaje fijo si no parsea o si no trae hora."""
    if not isinstance(value, str):
        raise InvalidContextError()
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    if "T" not in normalized:
        raise InvalidContextError()
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidContextError() from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce(enum_cls, value):
    if value is None or isinstance(value, enum_cls):
        return value
    return enum_cls(value)


class Phase(str, Enum):
    COMMAND = "COMMAND"
    PIN = "PIN"
    CONFIRMATION = "CONFIRMATION"


class DecisionType(str, Enum):
    REASK = "REASK"
    ASK_RECIPIENT = "ASK_RECIPIENT"
    ASK_PIN = "ASK_PIN"
    ASK_CONFIRM = "ASK_CONFIRM"
    REQUIRE_AUTH = "REQUIRE_AUTH"
    PAY = "PAY"
    REJECT = "REJECT"


class Reason(str, Enum):
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    INTENT_UNKNOWN = "INTENT_UNKNOWN"
    AMOUNT_ERROR = "AMOUNT_ERROR"
    INTENT_AMBIGUOUS = "INTENT_AMBIGUOUS"
    AMOUNT_MISSING = "AMOUNT_MISSING"
    RECIPIENT_MISSING = "RECIPIENT_MISSING"
    INTENT_UNCLEAR = "INTENT_UNCLEAR"
    INTENT_LOW_CONFIDENCE = "INTENT_LOW_CONFIDENCE"
    TRANSCRIPT_LOW_CONFIDENCE = "TRANSCRIPT_LOW_CONFIDENCE"
    RECIPIENT_NOT_FOUND = "RECIPIENT_NOT_FOUND"
    RECIPIENT_AMBIGUOUS = "RECIPIENT_AMBIGUOUS"
    NO_BUDGET_GRANT = "NO_BUDGET_GRANT"
    PENDING_PAYMENT_SAME_RECIPIENT = "PENDING_PAYMENT_SAME_RECIPIENT"
    PENDING_PAYMENT_UNCONFIRMED = "PENDING_PAYMENT_UNCONFIRMED"
    VOICE_NOT_VERIFIED = "VOICE_NOT_VERIFIED"
    NEW_RECIPIENT = "NEW_RECIPIENT"
    HIGH_AMOUNT = "HIGH_AMOUNT"
    ALL_CHECKS_PASSED = "ALL_CHECKS_PASSED"
    PIN_LOCKED = "PIN_LOCKED"
    PIN_CORRECT = "PIN_CORRECT"
    PIN_WRONG = "PIN_WRONG"
    PIN_ATTEMPTS_EXHAUSTED = "PIN_ATTEMPTS_EXHAUSTED"
    PIN_INVALID_FORMAT = "PIN_INVALID_FORMAT"
    CONFIRMED = "CONFIRMED"
    CONFIRMED_NEEDS_WALLET_AUTH = "CONFIRMED_NEEDS_WALLET_AUTH"
    CONFIRMED_WITH_PIN = "CONFIRMED_WITH_PIN"
    USER_DECLINED = "USER_DECLINED"
    REPLY_UNCLEAR_ASK_AGAIN = "REPLY_UNCLEAR_ASK_AGAIN"
    REPLY_UNCLEAR_REJECTED = "REPLY_UNCLEAR_REJECTED"
    CHALLENGE_RETRY = "CHALLENGE_RETRY"
    CHALLENGE_FAILED = "CHALLENGE_FAILED"
    CHALLENGE_VOICE_NOT_VERIFIED = "CHALLENGE_VOICE_NOT_VERIFIED"


class IntentAction(str, Enum):
    PAY = "PAY"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"


class IntentStatus(str, Enum):
    OK = "OK"
    AMBIGUOUS = "AMBIGUOUS"
    UNCLEAR = "UNCLEAR"


class AmountError(str, Enum):
    TOO_MANY_DECIMALS = "TOO_MANY_DECIMALS"
    AMBIGUOUS_AMOUNT = "AMBIGUOUS_AMOUNT"
    INVALID_AMOUNT = "INVALID_AMOUNT"


class ResolutionKind(str, Enum):
    RESOLVED = "RESOLVED"
    CHOICE = "CHOICE"
    NOT_FOUND = "NOT_FOUND"


class VoiceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class PendingPaymentStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Reply(str, Enum):
    YES = "YES"
    NO = "NO"
    UNCLEAR = "UNCLEAR"


class PinVerifyResult(str, Enum):
    OK = "OK"
    WRONG = "WRONG"
    INVALID_FORMAT = "INVALID_FORMAT"


class ConfirmationMode(str, Enum):
    REPLY = "REPLY"
    CHALLENGE = "CHALLENGE"


def _fraction_or_none(value, campo):
    """Número en [0, 1] o None; sin bool, NaN ni infinito."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{campo} debe ser un número en [0, 1] o None")
    v = float(value)
    if math.isnan(v) or math.isinf(v) or not 0.0 <= v <= 1.0:
        raise ValueError(f"{campo} debe estar en [0, 1]")
    return v


@dataclass(frozen=True)
class Amount:
    value: str
    assetCode: str
    assetScale: int

    def __post_init__(self):
        if not isinstance(self.value, str) or not _AMOUNT_VALUE_RE.fullmatch(self.value):
            raise ValueError("Amount.value debe ser un string de solo dígitos (CONV-1)")


@dataclass(frozen=True)
class Intent:
    action: IntentAction
    amount: Amount | None
    amountError: AmountError | None
    recipient: str | None
    status: IntentStatus

    def __post_init__(self):
        object.__setattr__(self, "action", _coerce(IntentAction, self.action))
        object.__setattr__(self, "amountError", _coerce(AmountError, self.amountError))
        object.__setattr__(self, "status", _coerce(IntentStatus, self.status))


@dataclass(frozen=True)
class Contact:
    alias: str
    name: str
    walletAddress: str
    previouslyPaid: bool


@dataclass(frozen=True)
class AgendaOption:
    alias: str
    name: str


@dataclass(frozen=True)
class Resolution:
    kind: ResolutionKind
    contact: Contact | None = None
    options: tuple[AgendaOption, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "kind", _coerce(ResolutionKind, self.kind))
        if self.kind is ResolutionKind.RESOLVED and self.contact is None:
            raise ValueError("resolution RESOLVED requiere contact")


@dataclass(frozen=True)
class Voice:
    status: VoiceStatus
    score: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "status", _coerce(VoiceStatus, self.status))


@dataclass(frozen=True)
class Quote:
    debitAmount: Amount
    receiveAmount: Amount
    exceedsRemaining: bool


@dataclass(frozen=True)
class PendingPayment:
    recipient: str
    createdAt: str
    status: PendingPaymentStatus

    def __post_init__(self):
        object.__setattr__(self, "status", _coerce(PendingPaymentStatus, self.status))


@dataclass(frozen=True)
class PinContext:
    result: PinVerifyResult | None
    sessionFailures: int
    locked: bool

    def __post_init__(self):
        object.__setattr__(self, "result", _coerce(PinVerifyResult, self.result))


@dataclass(frozen=True)
class Confirmation:
    """Confirmación del turno (B11). El MODO lo decide el orquestador
    (`config.confirmationChallenge` es suya, no del motor, SEG-3).

    `phrase_score` es el resultado de `phrase_match` de Voz (None = no hubo
    respuesta por voz); la coincidencia de texto la calcula Voz, no el motor.
    `challenge_attempts` cuenta los desafíos repetidos (regla 4 del spec).
    """
    mode: ConfirmationMode
    phrase_score: float | None
    voice: Voice | None
    challenge_attempts: int

    def __post_init__(self):
        object.__setattr__(self, "mode", _coerce(ConfirmationMode, self.mode))
        object.__setattr__(self, "phrase_score", _fraction_or_none(self.phrase_score, "phrase_score"))
        if self.voice is not None and not isinstance(self.voice, Voice):
            raise ValueError("confirmation.voice debe ser Voice o None")
        if isinstance(self.challenge_attempts, bool) or not isinstance(self.challenge_attempts, int) \
                or self.challenge_attempts < 0:
            raise ValueError("challenge_attempts debe ser un int >= 0")


@dataclass(frozen=True)
class EngineConfig:
    highAmountThreshold: Amount | None
    pendingWindowSeconds: int
    minIntentConfidence: float | None
    minTranscriptConfidence: float | None
    confirmation_challenge: bool = False
    challenge_phrase_match_min: float = 0.80

    def __post_init__(self):
        if not isinstance(self.confirmation_challenge, bool):
            raise ValueError("confirmation_challenge debe ser bool")
        minimo = _fraction_or_none(self.challenge_phrase_match_min, "challenge_phrase_match_min")
        if minimo is None:
            raise ValueError("challenge_phrase_match_min no puede ser None")
        object.__setattr__(self, "challenge_phrase_match_min", float(minimo))


@dataclass(frozen=True)
class Context:
    phase: Phase
    intent: Intent
    resolution: Resolution
    voice: Voice
    enrolled: bool
    hasBudgetGrant: bool
    quote: Quote | None
    pendingPayment: PendingPayment | None
    now: str
    reply: Reply | None
    unclearReplies: int
    pin: PinContext
    transcriptConfidence: float | None
    intentConfidence: float | None
    config: EngineConfig
    confirmation: Confirmation | None = None

    def __post_init__(self):
        object.__setattr__(self, "phase", _coerce(Phase, self.phase))
        object.__setattr__(self, "reply", _coerce(Reply, self.reply))
        if self.confirmation is not None and not isinstance(self.confirmation, Confirmation):
            raise ValueError("confirmation debe ser Confirmation o None")


@dataclass(frozen=True)
class Decision:
    decision: DecisionType
    reason: Reason

    def __post_init__(self):
        object.__setattr__(self, "decision", _coerce(DecisionType, self.decision))
        object.__setattr__(self, "reason", _coerce(Reason, self.reason))

    def to_dict(self) -> dict:
        """Forma del `Decision` para el orquestador: {"decision", "reason"}."""
        return {"decision": self.decision.value, "reason": self.reason.value}