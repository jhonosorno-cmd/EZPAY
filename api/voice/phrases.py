"""Textos que dice el sistema (`say`): solo plantillas de docs/voz/contrato-voz.md §7, nunca un LLM.

Español, tuteo, sin género. Los montos se formatean desde `Amount` con format_amount (sin float) y la
palabra de la moneda sale de la configuración (CURRENCY_WORDS), no de la plantilla.
"""
import re
from enum import Enum

from voice.amounts import Amount, format_amount
from voice.config import CURRENCY_WORDS


class Situation(str, Enum):
    NO_SPEECH = "NO_SPEECH"
    NOT_UNDERSTOOD = "NOT_UNDERSTOOD"
    AMOUNT_MISSING = "AMOUNT_MISSING"
    RECIPIENT_MISSING = "RECIPIENT_MISSING"
    AMOUNT_AMBIGUOUS = "AMOUNT_AMBIGUOUS"
    TOO_MANY_DECIMALS = "TOO_MANY_DECIMALS"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    NOT_FOUND = "NOT_FOUND"
    CHOICE = "CHOICE"
    NEAR = "NEAR"
    CONFIRM = "CONFIRM"
    CONFIRM_UNCLEAR = "CONFIRM_UNCLEAR"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    PIN_KEYBOARD = "PIN_KEYBOARD"
    AUTH_BUDGET = "AUTH_BUDGET"
    AUTH_OVERRUN = "AUTH_OVERRUN"
    AUTH_REDIRECT = "AUTH_REDIRECT"
    AUTH_APPROVED = "AUTH_APPROVED"
    AUTH_REJECTED = "AUTH_REJECTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"


S = Situation
TEMPLATES = {
    S.NO_SPEECH: "No te escuché. ¿Me lo repites?",
    S.NOT_UNDERSTOOD: "No te entendí. ¿Me lo repites?",
    S.AMOUNT_MISSING: "¿Cuánto quieres enviar?",
    S.RECIPIENT_MISSING: "¿A quién se lo envío?",
    S.AMOUNT_AMBIGUOUS: "No me quedó claro el monto. ¿Me lo dices otra vez?",
    S.TOO_MANY_DECIMALS: "Solo puedo enviar montos con hasta {n}. ¿Me lo dices otra vez?",
    S.INVALID_AMOUNT: "Ese monto no es válido. ¿Cuánto quieres enviar?",
    S.NOT_FOUND: "No encontré a {destinatario} en tu agenda.",
    S.CHOICE: "¿A cuál? {opciones}.",
    S.NEAR: "¿Quisiste decir {nombre}?",
    S.CONFIRM: "¿Le envío {recibe} {moneda} a {nombre}?",
    S.CONFIRM_UNCLEAR: "No te entendí. ¿Le envío {recibe} {moneda} a {nombre}? Di sí o no.",
    S.CANCELLED: "Listo, cancelé el envío.",
    S.COMPLETED: "Listo, le envié {recibe} {moneda} a {nombre}.",
    S.PIN_KEYBOARD: "Escribe tu PIN en el teclado.",
    S.AUTH_BUDGET: "Para empezar, autoriza tu presupuesto en tu billetera. Toca el botón que dice Aprobar.",
    S.AUTH_OVERRUN: "Supera tu presupuesto. ¿Lo autorizas en tu billetera?",
    S.AUTH_REDIRECT: "Te voy a llevar a tu billetera. Toca el botón que dice Aprobar.",
    S.AUTH_APPROVED: "Listo, autorizaste el pago.",
    S.AUTH_REJECTED: "No autorizaste el pago. No envié nada.",
    S.PAYMENT_PENDING: "Tu envío está en camino. No hace falta repetirlo.",
}
NO_DECIMALS = "Solo puedo enviar montos sin decimales. ¿Me lo dices otra vez?"
NOT_FOUND_GENERIC = "No encontré a esa persona en tu agenda."
COST_SUFFIX = " Te costó {costo} {moneda}."
REQUIRED = {
    S.TOO_MANY_DECIMALS: {"scale"},
    S.NOT_FOUND: {"spoken"},
    S.CHOICE: {"names"},
    S.NEAR: {"name"},
    S.CONFIRM: {"amount", "name"},
    S.CONFIRM_UNCLEAR: {"amount", "name"},
    S.COMPLETED: {"amount", "name"},
}
OPTIONAL = {S.COMPLETED: {"debit"}}
# Lo que dijo la persona solo se repite si son hasta 4 palabras de letras (nunca URL, números ni texto largo).
_SAFE_SPOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){0,3}")
MAX_SPOKEN_CHARS = 40


def _money(amount: Amount) -> tuple[str, str]:
    if amount.asset_code not in CURRENCY_WORDS:
        raise ValueError(f"no currency word configured for {amount.asset_code!r}")
    return format_amount(amount), CURRENCY_WORDS[amount.asset_code]


def _name(value) -> str:
    """Nombre de un contacto: texto no vacío. Una confirmación nunca sale sin destinatario (SEG-2)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"name must be a non-empty string, got {value!r}")
    return value.strip()


def _amount(value) -> Amount:
    if not isinstance(value, Amount):
        raise ValueError(f"expected an Amount, got {type(value).__name__}")
    return value


def say(situation: Situation, **params) -> str:
    """Texto en español para `situation`. Parámetros faltantes o de más -> ValueError (error del programa)."""
    situation = Situation(situation)
    required = REQUIRED.get(situation, set())
    allowed = required | OPTIONAL.get(situation, set())
    if not required <= params.keys() or not params.keys() <= allowed:
        raise ValueError(f"{situation.value} needs {sorted(required)}, got {sorted(params)}")
    if situation is S.TOO_MANY_DECIMALS:
        n = params["scale"]
        if type(n) is not int or n < 0:
            raise ValueError(f"scale must be an int >= 0, got {n!r}")
        return NO_DECIMALS if n == 0 else TEMPLATES[situation].format(n="1 decimal" if n == 1 else f"{n} decimales")
    if situation is S.NOT_FOUND:
        spoken = params["spoken"]
        ok = isinstance(spoken, str) and len(spoken.strip()) <= MAX_SPOKEN_CHARS and _SAFE_SPOKEN.fullmatch(spoken.strip())
        return TEMPLATES[situation].format(destinatario=spoken.strip()) if ok else NOT_FOUND_GENERIC
    if situation is S.CHOICE:
        raw = params["names"]
        names = [_name(n) for n in raw] if not isinstance(raw, str) else []
        if len(names) < 2:
            raise ValueError("CHOICE needs a list of at least 2 names; use NEAR for one")
        return TEMPLATES[situation].format(opciones=", ".join(names[:-1]) + " o " + names[-1])
    if situation is S.NEAR:
        return TEMPLATES[situation].format(nombre=_name(params["name"]))
    if situation in (S.CONFIRM, S.CONFIRM_UNCLEAR, S.COMPLETED):
        amount = _amount(params["amount"])
        recibe, moneda = _money(amount)
        text = TEMPLATES[situation].format(recibe=recibe, moneda=moneda, nombre=_name(params["name"]))
        debit = params.get("debit")
        if debit is not None:
            debit = _amount(debit)
            if (debit.asset_code, debit.asset_scale) != (amount.asset_code, amount.asset_scale):
                raise ValueError("debit and amount must share assetCode and assetScale")
            if debit.value != amount.value:
                text += COST_SUFFIX.format(costo=format_amount(debit), moneda=moneda)
        return text
    return TEMPLATES[situation]
