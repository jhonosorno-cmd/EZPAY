"""Motor de decisión del flujo de pago por voz (ML 2).

Expone `decide(context) -> Decision` (función pura), los tipos del `Context`
(incluida la `Confirmation` del desafío de voz, B11) y
`say_situation(decision, context)`: el nombre de la situación del catálogo
de Voz (`voice/phrases.py`, único dueño de los textos de `say`).
"""
from .context_io import decide_dict, parse_context
from .engine import decide
from .models import (
    AgendaOption,
    Amount,
    AmountError,
    Confirmation,
    ConfirmationMode,
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
from .say_map import (PENDING_VOZ_SITUATIONS, VOICE_SITUATIONS_EXISTING,
                      VOICE_SITUATIONS_NEW, say_situation)

__all__ = [
    "decide",
    "decide_dict",
    "parse_context",
    "say_situation",
    "VOICE_SITUATIONS_EXISTING",
    "VOICE_SITUATIONS_NEW",
    "PENDING_VOZ_SITUATIONS",
    "AgendaOption",
    "Amount",
    "AmountError",
    "Confirmation",
    "ConfirmationMode",
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