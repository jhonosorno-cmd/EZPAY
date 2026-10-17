"""Motor de decisión del flujo de pago por voz.

Spec: openspec/changes/add-decision-engine/specs/decision-engine/spec.md.
Función pura `decide(context) -> Decision` (D1): sin HTTP, sin reloj ni azar
propios (la hora llega en context.now), determinista. Tabla de reglas ordenada
por fase (D2): gana la primera regla que aplica. El mapeo a TurnState lo hace el
orquestador, no el motor.
"""
from datetime import datetime, timezone

from .models import (
    Context,
    Decision,
    DecisionType,
    IntentAction,
    IntentStatus,
    InvalidContextError,
    AmountError,
    parse_instant,
    PendingPaymentStatus,
    Phase,
    PinVerifyResult,
    Reason,
    ResolutionKind,
    Reply,
    VoiceStatus,
)


def _pending_flags(context) -> tuple[bool, bool]:
    """(abierta dentro de la ventana, pasada la ventana) para las reglas 6 y 6b.

    "Mismo destinatario" se compara por wallet address resuelta (decidido
    2026-10-16); "abierta" corresponde a status PROCESSING.
    """
    pending = context.pendingPayment
    if pending is None or pending.status is not PendingPaymentStatus.PROCESSING:
        return False, False
    if context.resolution.kind is not ResolutionKind.RESOLVED or context.resolution.contact is None:
        return False, False
    if pending.recipient != context.resolution.contact.walletAddress:
        return False, False
    elapsed = (parse_instant(context.now) - parse_instant(pending.createdAt)).total_seconds()
    window = context.config.pendingWindowSeconds
    return elapsed <= window, elapsed > window


def _is_high_amount(receive_amount, threshold) -> bool:
    # Montos como enteros, nunca float (CONV-1). Moneda o escala distinta al
    # umbral: cuenta como alto (falla hacia el lado seguro).
    if threshold is None:
        return False
    if receive_amount.assetCode != threshold.assetCode or receive_amount.assetScale != threshold.assetScale:
        return True
    return int(receive_amount.value) >= int(threshold.value)


def _decide_command(context) -> Decision:
    intent = context.intent

    if intent.action is IntentAction.CANCEL:
        return Decision(DecisionType.REJECT, Reason.CANCELLED_BY_USER)

    if (
        intent.status is not IntentStatus.OK
        or intent.action is IntentAction.UNKNOWN
        or intent.amountError is not None
        or intent.amount is None
        or intent.recipient is None
    ):
        if intent.action is IntentAction.UNKNOWN:
            reason = Reason.INTENT_UNKNOWN
        elif intent.amountError is not None:
            reason = Reason.AMOUNT_ERROR
        elif intent.status is IntentStatus.AMBIGUOUS:
            reason = Reason.INTENT_AMBIGUOUS
        elif intent.amount is None:
            reason = Reason.AMOUNT_MISSING
        elif intent.recipient is None:
            reason = Reason.RECIPIENT_MISSING
        else:
            reason = Reason.INTENT_UNCLEAR
        return Decision(DecisionType.REASK, reason)

    config = context.config
    if (
        config.minIntentConfidence is not None
        and context.intentConfidence is not None
        and context.intentConfidence < config.minIntentConfidence
    ):
        return Decision(DecisionType.REASK, Reason.INTENT_LOW_CONFIDENCE)
    if (
        config.minTranscriptConfidence is not None
        and context.transcriptConfidence is not None
        and context.transcriptConfidence < config.minTranscriptConfidence
    ):
        return Decision(DecisionType.REASK, Reason.TRANSCRIPT_LOW_CONFIDENCE)

    if context.resolution.kind is ResolutionKind.NOT_FOUND:
        return Decision(DecisionType.REASK, Reason.RECIPIENT_NOT_FOUND)
    if context.resolution.kind is ResolutionKind.CHOICE:
        return Decision(DecisionType.ASK_RECIPIENT, Reason.RECIPIENT_AMBIGUOUS)

    if not context.hasBudgetGrant:
        return Decision(DecisionType.REQUIRE_AUTH, Reason.NO_BUDGET_GRANT)
    if context.quote is None:
        raise InvalidContextError()

    within_window, past_window = _pending_flags(context)
    if within_window:
        return Decision(DecisionType.REASK, Reason.PENDING_PAYMENT_SAME_RECIPIENT)

    if context.voice.status is not VoiceStatus.VERIFIED:
        return Decision(DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED)

    if not context.quote.exceedsRemaining:
        contact = context.resolution.contact
        if contact is not None and not contact.previouslyPaid:
            return Decision(DecisionType.ASK_PIN, Reason.NEW_RECIPIENT)
        if _is_high_amount(context.quote.receiveAmount, config.highAmountThreshold):
            return Decision(DecisionType.ASK_PIN, Reason.HIGH_AMOUNT)

    reason = Reason.PENDING_PAYMENT_UNCONFIRMED if past_window else Reason.ALL_CHECKS_PASSED
    return Decision(DecisionType.ASK_CONFIRM, reason)


def _decide_pin(context) -> Decision:
    pin = context.pin
    if pin.locked:
        return Decision(DecisionType.REJECT, Reason.PIN_LOCKED)
    if pin.result is PinVerifyResult.OK:
        _, past_window = _pending_flags(context)
        reason = Reason.PENDING_PAYMENT_UNCONFIRMED if past_window else Reason.PIN_CORRECT
        return Decision(DecisionType.ASK_CONFIRM, reason)
    if pin.result is PinVerifyResult.WRONG:
        if pin.sessionFailures < 3:
            return Decision(DecisionType.ASK_PIN, Reason.PIN_WRONG)
        return Decision(DecisionType.REJECT, Reason.PIN_ATTEMPTS_EXHAUSTED)
    return Decision(DecisionType.ASK_PIN, Reason.PIN_INVALID_FORMAT)


def _decide_confirmation(context) -> Decision:
    reply = context.reply
    if reply is Reply.YES:
        if context.quote is None:
            raise InvalidContextError()
        if context.quote.exceedsRemaining:
            return Decision(DecisionType.REQUIRE_AUTH, Reason.CONFIRMED_NEEDS_WALLET_AUTH)
        return Decision(DecisionType.PAY, Reason.CONFIRMED)
    if reply is Reply.NO:
        return Decision(DecisionType.REJECT, Reason.USER_DECLINED)
    if context.unclearReplies == 0:
        return Decision(DecisionType.ASK_CONFIRM, Reason.REPLY_UNCLEAR_ASK_AGAIN)
    return Decision(DecisionType.REJECT, Reason.REPLY_UNCLEAR_REJECTED)


def decide(context: Context) -> Decision:
    if context.phase is Phase.COMMAND:
        return _decide_command(context)
    if context.phase is Phase.PIN:
        return _decide_pin(context)
    if context.phase is Phase.CONFIRMATION:
        return _decide_confirmation(context)
    raise ValueError("unknown phase")