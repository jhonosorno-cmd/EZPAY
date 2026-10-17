"""Motor de decisión del flujo de pago por voz (ML 2, hito H1).

Expone `decide(context) -> Decision` (función pura), los tipos del `Context`
y la tabla de plantillas de `say` por `reason` (solo datos).
"""
from .context_io import decide_dict, parse_context
from .engine import decide
from .models import (
    AgendaOption,
    Amount,
    AmountError,
    Contact,
    Context,
    Decision,
    DecisionType,
    EngineConfig,
    Intent,
    IntentAction,
    IntentStatus,
    InvalidContextError,
    PendingPayment,
    PendingPaymentStatus,
    Phase,
    PinContext,
    PinVerifyResult,
    Quote,
    Reason,
    Reply,
    Resolution,
    ResolutionKind,
    Voice,
    VoiceStatus,
)
from .templates import SAY_TEMPLATES

__all__ = [
    "decide",
    "decide_dict",
    "parse_context",
    "SAY_TEMPLATES",
    "AgendaOption",
    "Amount",
    "AmountError",
    "Contact",
    "Context",
    "Decision",
    "DecisionType",
    "EngineConfig",
    "Intent",
    "IntentAction",
    "IntentStatus",
    "InvalidContextError",
    "PendingPayment",
    "PendingPaymentStatus",
    "Phase",
    "PinContext",
    "PinVerifyResult",
    "Quote",
    "Reason",
    "Reply",
    "Resolution",
    "ResolutionKind",
    "Voice",
    "VoiceStatus",
]