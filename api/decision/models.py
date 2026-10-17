"""Tipos del motor de decisión.

Espec fuente: openspec/changes/add-decision-engine/specs/decision-engine/spec.md,
requisito "El contexto de entrada" (decidido 2026-10-16 con ML 2, ML 1 y Pagos).
Los montos se comparan como enteros (CONV-1): Amount.value es un string de solo dígitos.
"""
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
    USER_DECLINED = "USER_DECLINED"
    REPLY_UNCLEAR_ASK_AGAIN = "REPLY_UNCLEAR_ASK_AGAIN"
    REPLY_UNCLEAR_REJECTED = "REPLY_UNCLEAR_REJECTED"


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
class EngineConfig:
    highAmountThreshold: Amount | None
    pendingWindowSeconds: int
    minIntentConfidence: float | None
    minTranscriptConfidence: float | None


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

    def __post_init__(self):
        object.__setattr__(self, "phase", _coerce(Phase, self.phase))
        object.__setattr__(self, "reply", _coerce(Reply, self.reply))


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