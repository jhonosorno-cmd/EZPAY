"""`say_situation(decision, context) -> str | None`: situación del catálogo de Voz.

El catálogo de `say` vive SOLO en `voice/phrases.py` (ML 1): aquí no hay textos.
Esta función devuelve el NOMBRE de la situación; el orquestador llama
`voice.phrases.say(Situation(nombre), **params)` con los parámetros del turno
(monto, contacto, escala de decimales...). `CONFIRMED` (y `CONFIRMED_WITH_PIN`,
B11) devuelve `None`: el `say` sale del resultado del pago (`COMPLETED`,
`AUTH_APPROVED`, `PAYMENT_PENDING`...).

Situaciones que Voz ya tiene hoy: `VOICE_SITUATIONS_EXISTING` (21, enum
`Situation` de `voice/phrases.py`). Situaciones NUEVAS que Voz agregará para
cubrir razones del motor que hoy no tienen plantilla: `VOICE_SITUATIONS_NEW`
(17: 13 + las 4 del desafío de voz B11). De esas, `PENDING_VOZ_SITUATIONS`
son las que TODAVÍA no existen en `Situation` (son de Sebastián): si Voz
agrega una, hay que quitarla de ese set (hay una prueba que lo vigila).
"""
from .models import AmountError, ConfirmationMode, Context, Decision, InvalidContextError, Reason

VOICE_SITUATIONS_EXISTING = (
    "NO_SPEECH",
    "NOT_UNDERSTOOD",
    "AMOUNT_MISSING",
    "RECIPIENT_MISSING",
    "AMOUNT_AMBIGUOUS",
    "TOO_MANY_DECIMALS",
    "INVALID_AMOUNT",
    "NOT_FOUND",
    "CHOICE",
    "NEAR",
    "CONFIRM",
    "CONFIRM_UNCLEAR",
    "CANCELLED",
    "COMPLETED",
    "PIN_KEYBOARD",
    "AUTH_BUDGET",
    "AUTH_OVERRUN",
    "AUTH_REDIRECT",
    "AUTH_APPROVED",
    "AUTH_REJECTED",
    "PAYMENT_PENDING",
)

VOICE_SITUATIONS_NEW = (
    "INTENT_AMBIGUOUS",
    "INTENT_LOW_CONFIDENCE",
    "TRANSCRIPT_LOW_CONFIDENCE",
    "PENDING_PAYMENT_SAME_RECIPIENT",
    "NEW_RECIPIENT",
    "HIGH_AMOUNT",
    "PIN_WRONG",
    "PIN_ATTEMPTS_EXHAUSTED",
    "PIN_LOCKED",
    "PIN_INVALID_FORMAT",
    "REPLY_UNCLEAR_REJECTED",
    "PENDING_PAYMENT_UNCONFIRMED",
    "PENDING_PAYMENT_UNCONFIRMED_OVERRUN",
    # B11: las 4 del desafío de voz (Sebastián las agrega a voice/phrases.py)
    "CONFIRM_CHALLENGE",
    "CONFIRM_CHALLENGE_OVERRUN",
    "CHALLENGE_RETRY",
    "CHALLENGE_FAILED",
)

# Situaciones NUEVAS que TODAVÍA no existen en voice/phrases.py (PENdientes de Voz).
# Voz ya agregó las 4 del desafío (17 oct): no queda ninguna pendiente.
PENDING_VOZ_SITUATIONS = frozenset()

_SAME_NAME_AS_REASON = frozenset(VOICE_SITUATIONS_NEW) - {
    "PENDING_PAYMENT_UNCONFIRMED",
    "PENDING_PAYMENT_UNCONFIRMED_OVERRUN",
}


def _exceeds_remaining(context: Context) -> bool:
    if context.quote is None:
        raise InvalidContextError()
    return context.quote.exceedsRemaining


def _modo_challenge(context: Context) -> bool:
    """confirmation presente y en modo CHALLENGE (B11); el modo lo arma el orquestador."""
    confirmation = context.confirmation
    return confirmation is not None and confirmation.mode is ConfirmationMode.CHALLENGE


def _con_o_sin_exceso(context: Context, normal: str, overrun: str) -> str:
    return overrun if _exceeds_remaining(context) else normal


def say_situation(decision: Decision, context: Context) -> str | None:
    """Nombre de la situación de Voz para el turno; `None` solo para CONFIRMED.

    Es función pura y fail-closed: una variante que necesita la `quote` (o el
    `amountError` u opciones de resolución) y no la tiene es contexto imposible
    y levanta `InvalidContextError` con mensaje fijo, sin datos del request.
    """
    reason = decision.reason
    if reason is Reason.CANCELLED_BY_USER:
        return "CANCELLED"
    if reason is Reason.INTENT_UNKNOWN:
        return "NOT_UNDERSTOOD"
    if reason is Reason.INTENT_UNCLEAR:
        return "NOT_UNDERSTOOD"
    if reason is Reason.AMOUNT_MISSING:
        return "AMOUNT_MISSING"
    if reason is Reason.RECIPIENT_MISSING:
        return "RECIPIENT_MISSING"
    if reason is Reason.AMOUNT_ERROR:
        error = context.intent.amountError
        if error is AmountError.TOO_MANY_DECIMALS:
            return "TOO_MANY_DECIMALS"
        if error is AmountError.AMBIGUOUS_AMOUNT:
            return "AMOUNT_AMBIGUOUS"
        if error is AmountError.INVALID_AMOUNT:
            return "INVALID_AMOUNT"
        raise InvalidContextError()
    if reason is Reason.RECIPIENT_NOT_FOUND:
        return "NOT_FOUND"
    if reason is Reason.RECIPIENT_AMBIGUOUS:
        options = len(context.resolution.options)
        if options >= 2:
            return "CHOICE"
        if options == 1:
            return "NEAR"
        raise InvalidContextError()
    if reason is Reason.NO_BUDGET_GRANT:
        return "AUTH_BUDGET"
    if reason is Reason.VOICE_NOT_VERIFIED:
        return "PIN_KEYBOARD"
    if reason is Reason.ALL_CHECKS_PASSED:
        if _modo_challenge(context):  # B11: la confirmación pide repetir la frase
            return _con_o_sin_exceso(context, "CONFIRM_CHALLENGE", "CONFIRM_CHALLENGE_OVERRUN")
        return "AUTH_OVERRUN" if _exceeds_remaining(context) else "CONFIRM"
    if reason is Reason.PIN_CORRECT:
        # el PIN correcto no lleva mapping del desafío: en CHALLENGE con frase
        # coincidente el motor emite CONFIRMED_WITH_PIN (PAY), no PIN_CORRECT
        return "AUTH_OVERRUN" if _exceeds_remaining(context) else "CONFIRM"
    if reason is Reason.PENDING_PAYMENT_UNCONFIRMED:
        if _modo_challenge(context):  # B11
            return _con_o_sin_exceso(context, "CONFIRM_CHALLENGE", "CONFIRM_CHALLENGE_OVERRUN")
        return _con_o_sin_exceso(context, "PENDING_PAYMENT_UNCONFIRMED", "PENDING_PAYMENT_UNCONFIRMED_OVERRUN")
    if reason is Reason.CONFIRMED or reason is Reason.CONFIRMED_WITH_PIN:  # B11: say del resultado del pago
        return None
    if reason is Reason.CONFIRMED_NEEDS_WALLET_AUTH:
        return "AUTH_REDIRECT"
    if reason is Reason.USER_DECLINED:
        return "CANCELLED"
    if reason is Reason.REPLY_UNCLEAR_ASK_AGAIN:
        return "CONFIRM_UNCLEAR"
    if reason is Reason.CHALLENGE_VOICE_NOT_VERIFIED:  # B11: pide PIN (la frase ya coincidió)
        return "PIN_KEYBOARD"
    if reason is Reason.CHALLENGE_RETRY or reason is Reason.CHALLENGE_FAILED:  # B11
        return reason.value
    if reason.value in _SAME_NAME_AS_REASON:
        return reason.value
    raise InvalidContextError()  # Reason es un enum cerrado: no se llega aquí