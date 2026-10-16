"""reply-classification: respuesta a una pregunta del sistema -> YES, NO o UNCLEAR.

Determinístico y sin LLM. Lista cerrada de docs/voz/contrato-voz.md §8: YES solo si todas las palabras
forman afirmaciones o rellenos permitidos y hay al menos una afirmación; NO solo si todas son negaciones
o rellenos. Cualquier otra cosa (duda, monto, destinatario, eco de la pregunta, mezcla) es UNCLEAR.
"""
import unicodedata
from enum import Enum

from voice.text import words


class Reply(str, Enum):
    YES = "YES"
    NO = "NO"
    UNCLEAR = "UNCLEAR"


AFFIRMATIONS = {("si",), ("confirmo",), ("dale",), ("claro", "que", "si"), ("si", "claro"),
                ("si", "por", "favor"), ("de", "acuerdo")}
NEGATIONS = {("no",), ("nada",), ("cancela",), ("cancelar",), ("para",), ("detente",)}
FILLERS = {("por", "favor"), ("gracias",)}
FILLER_WORDS = {"por", "favor", "gracias"}
MAX_REPLY_CHARS = 200


def _segments(tokens: list[str], phrases: set[tuple[str, ...]]) -> bool:
    """True si `tokens` se puede partir completo en frases de `phrases` (se permiten repeticiones)."""
    ok = [True] + [False] * len(tokens)
    for i in range(len(tokens)):
        if ok[i]:
            for p in phrases:
                if tuple(tokens[i:i + len(p)]) == p:
                    ok[i + len(p)] = True
    return ok[-1]


def classify_reply(text: str | None) -> Reply:
    """Clasifica la respuesta. Nunca lanza: una entrada que no es texto es UNCLEAR."""
    if not isinstance(text, str) or len(text) > MAX_REPLY_CHARS:
        return Reply.UNCLEAR
    if any(unicodedata.category(c)[0] == "C" and not c.isspace() for c in text):
        return Reply.UNCLEAR                               # control o formato invisible: no es un "sí" claro
    tokens = words(text)
    if not tokens or set(tokens) <= FILLER_WORDS:
        return Reply.UNCLEAR
    if _segments(tokens, AFFIRMATIONS | FILLERS):
        return Reply.YES
    if _segments(tokens, NEGATIONS | FILLERS):
        return Reply.NO
    return Reply.UNCLEAR
