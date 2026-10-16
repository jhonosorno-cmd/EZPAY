"""intent-extraction: texto de un comando -> Intent, solo con reglas (sin LLM; decisión de Sebastián,
2026-10-16).

Gramática: [prefijo] VERBO MONTO (a|para) DESTINATARIO  o  [prefijo] VERBO (a|para) DESTINATARIO MONTO.
El monto lo fija parse_amount. Todo lo que está fuera de la gramática es UNKNOWN (sin verbo de pago) o
PAY con status UNCLEAR: nunca un pago con status OK. Todo status distinto de OK es "no pagar".
"""
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from voice.amounts import SLANG_WORDS, UNITS, Amount, AmountError, AssetConfig, parse_amount
from voice.text import fold


class Action(str, Enum):
    PAY = "PAY"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"


class Status(str, Enum):
    OK = "OK"
    AMBIGUOUS = "AMBIGUOUS"
    UNCLEAR = "UNCLEAR"


@dataclass(frozen=True)
class Intent:
    action: Action
    amount: Amount | None
    amount_error: AmountError | None
    recipient: str | None
    status: Status


PAY_VERBS = {
    "envia", "enviale", "enviales", "envie", "enviele", "envieles", "enviar", "enviarle", "enviarles",
    "manda", "mandale", "mandales", "mande", "mandele", "mandar", "mandarle",
    "pasa", "pasale", "pase", "pasele", "pasar", "pasarle",
    "paga", "pagale", "pague", "paguele", "pagar", "pagarle",
    "transfiere", "transfierele", "transfiera", "transfierale", "transferir", "transferirle",
    "consigna", "consignale", "consigne", "consignele", "consignar", "consignarle",
}
CANCEL_VERBS = {"cancela", "cancelar", "cancelalo", "cancele", "cancelelo", "olvida", "olvidalo",
                "olvidelo", "deja", "dejalo", "dejelo", "para", "detente", "nada"}
CANCEL_FILLERS = {"no", "mejor", "asi", "ya", "eso", "el", "envio", "pago", "todo", "mas"}
PREFIXES = (("quiero",), ("quisiera",), ("necesito",), ("me", "gustaria"))
COURTESY = (("por", "favor"), ("porfa",), ("porfavor",))
PREPOSITIONS = {"a", "para"}
NUMBER_WORDS = set(UNITS) | {"mil", "millon", "millones", "medio"}
AMOUNT_WORDS = NUMBER_WORDS | {"y", "peso", "pesos", "cop", "de", "$"} | SLANG_WORDS
_NUMERIC = re.compile(r"\$?[0-9][0-9.,]*")
_WALLET_LIKE = re.compile(r"https?:|://|www\.|@|\$[a-z]")
_SENTENCE_END = re.compile(r"(?<![0-9])\.|\.(?![0-9])|[?!;:]")
_SOFT_COMMA = re.compile(r"(?<![0-9]),|,(?![0-9])")
_WORD_HYPHEN = re.compile(r"(?<=[a-z])-(?=[a-z])")
_SPACE_PUNCT = re.compile(r"[\s\"'()\[\]¿¡…]+")
_OTHER = re.compile(r"[^a-z0-9.,$| ]")
MAX_COMMAND_CHARS = 200
MAX_RECIPIENT_WORDS = 5

_NOT_A_COMMAND = Intent(Action.UNKNOWN, None, None, None, Status.UNCLEAR)


def _drop(tokens: list[str], phrases) -> list[str]:
    out, i = [], 0
    while i < len(tokens):
        p = next((p for p in phrases if tuple(tokens[i:i + len(p)]) == p), None)
        if p:
            i += len(p)
        else:
            out.append(tokens[i])
            i += 1
    return out


def _sentences(text: str) -> list[list[str]]:
    """Oraciones como listas de palabras. Un carácter raro (dígito no ASCII, ancho cero, letra de otro
    alfabeto) queda como '#', que no es verbo, ni monto, ni destinatario válido."""
    t = fold(text)
    t = "".join("#" if ord(c) > 127 and unicodedata.category(c)[0] in "NLC" else c for c in t)
    t = _SENTENCE_END.sub("|", t)
    t = _SOFT_COMMA.sub(" ", t)
    t = _WORD_HYPHEN.sub(" ", t)                           # "laura-vecina"; "-20" queda como "#20"
    t = _SPACE_PUNCT.sub(" ", t)
    t = _OTHER.sub("#", t)
    return [s for s in (_drop(part.split(), COURTESY) for part in t.split("|")) if s]


def _is_cancel(tokens: list[str]) -> bool:
    return set(tokens) <= CANCEL_VERBS | CANCEL_FILLERS and bool(set(tokens) & CANCEL_VERBS)


def _after_verb(tokens: list[str]) -> list[str] | None:
    """Lo que sigue al verbo de pago (después de un prefijo opcional), o None si no empieza con uno."""
    i = 0
    while p := next((p for p in PREFIXES if tuple(tokens[i:i + len(p)]) == p), None):
        i += len(p)
    return tokens[i + 1:] if i < len(tokens) and tokens[i] in PAY_VERBS else None


def _amountish(t: str) -> bool:
    return t in AMOUNT_WORDS or _NUMERIC.fullmatch(t) is not None


def _numeric(t: str) -> bool:
    return t in NUMBER_WORDS or _NUMERIC.fullmatch(t) is not None


def _split(rest: list[str]) -> tuple[list[str], list[str] | None]:
    """(palabras del monto, palabras del destinatario o None si no hay preposición)."""
    idx = next((i for i, t in enumerate(rest) if t in PREPOSITIONS), None)
    if idx is None:
        return rest, None
    if idx > 0:
        return rest[:idx], rest[idx + 1:]
    after, k = rest[1:], len(rest) - 1
    while k > 0 and _amountish(after[k - 1]):
        k -= 1
    if not any(_numeric(t) for t in after[k:]):
        return [], after
    return after[k:], after[:k]


def _recipient(tokens: list[str] | None) -> tuple[str | None, Status]:
    if not tokens:
        return None, Status.UNCLEAR
    if any(t == "y" or t in PREPOSITIONS for t in tokens):
        return None, Status.AMBIGUOUS                      # más de un destinatario
    if any(_NUMERIC.fullmatch(t) or t in ("mil", "millon", "millones") for t in tokens):
        return None, Status.AMBIGUOUS                      # otro monto después del destinatario
    if any(t == "no" or t in CANCEL_VERBS for t in tokens):
        return None, Status.UNCLEAR                        # "…a Laura, cancela": la persona se retractó
    if len(tokens) > MAX_RECIPIENT_WORDS or not all(t.isascii() and t.isalpha() for t in tokens):
        return None, Status.UNCLEAR
    return " ".join(tokens), Status.OK


def _two_amounts(tokens: list[str], cfg: AssetConfig) -> bool:
    for i in range(1, len(tokens)):
        left, right = tokens[:i], tokens[i:]
        left = left[:-1] if left[-1] == "y" else left
        right = right[1:] if right[0] == "y" else right
        if left and right and parse_amount(" ".join(left), cfg).ok and parse_amount(" ".join(right), cfg).ok:
            return True
    return False


def _amount(tokens: list[str], cfg: AssetConfig) -> tuple[Amount | None, AmountError | None, Status]:
    if not any(_numeric(t) for t in tokens):
        return None, None, Status.UNCLEAR                  # sin monto ("plata", nada)
    if not all(_amountish(t) for t in tokens):
        return None, None, Status.UNCLEAR                  # el monto trae otras palabras
    r = parse_amount(" ".join(tokens), cfg)
    if r.ok:
        return r.amount, None, Status.OK
    if r.code is AmountError.AMBIGUOUS_AMOUNT and _two_amounts(tokens, cfg):
        return None, None, Status.AMBIGUOUS                # más de un monto
    return None, r.code, Status.UNCLEAR


def extract_intent(text: str | None, cfg: AssetConfig) -> Intent:
    """Intención de un comando. Nunca lanza; no llama a ningún servicio ni modifica estado."""
    if not isinstance(text, str) or len(text) > MAX_COMMAND_CHARS or not text.strip():
        return _NOT_A_COMMAND
    sentences = _sentences(text)
    if not sentences:
        return _NOT_A_COMMAND
    pay = [s for s in sentences if _after_verb(s) is not None]
    if len(sentences) > 1:
        if pay:
            return Intent(Action.PAY, None, None, None, Status.UNCLEAR)
        if all(_is_cancel(s) for s in sentences):
            return Intent(Action.CANCEL, None, None, None, Status.OK)
        return Intent(Action.UNKNOWN, None, None, None, Status.OK)
    if _is_cancel(sentences[0]):
        return Intent(Action.CANCEL, None, None, None, Status.OK)
    rest = _after_verb(sentences[0])
    if rest is None:
        return Intent(Action.UNKNOWN, None, None, None, Status.OK)
    if _WALLET_LIKE.search(fold(text)):
        return Intent(Action.PAY, None, None, None, Status.UNCLEAR)
    amount_tokens, recipient_tokens = _split(rest)
    recipient, recipient_status = _recipient(recipient_tokens)
    amount, error, amount_status = _amount(amount_tokens, cfg)
    statuses = {recipient_status, amount_status}
    status = Status.AMBIGUOUS if Status.AMBIGUOUS in statuses else Status.OK if statuses == {Status.OK} else Status.UNCLEAR
    if Status.AMBIGUOUS in (amount_status, recipient_status) and recipient is None and recipient_tokens \
            and any(_numeric(t) for t in recipient_tokens):
        amount = None                                      # otro monto después del destinatario
    if amount_status is Status.AMBIGUOUS:
        amount = None
    return Intent(Action.PAY, amount, error, recipient, status)
