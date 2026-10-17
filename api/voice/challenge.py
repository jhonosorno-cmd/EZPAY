"""confirmation-challenge: banco de frases, elección sin repetir y coincidencia de la frase pedida.

El backend elige la frase al azar (nunca un LLM) y la respuesta se compara con `phrase_match`; la voz de la
respuesta la verifica ML 2. Sin red ni disco, salvo la lectura del banco (un archivo de datos).
"""
import json
from pathlib import Path

from voice.config import (CHALLENGE_BANK_PATH, CHALLENGE_MAX_WORDS, CHALLENGE_MIN_MATCH, CHALLENGE_MIN_PHRASES,
                          CHALLENGE_MIN_WORDS)
from voice.text import words

# Palabras que el banco no puede contener: afirmaciones, negaciones, verbos de pago y palabras de monto.
FORBIDDEN_WORDS = frozenset({
    "si", "no", "confirmo", "dale", "claro", "listo", "nada", "cancela", "cancelar", "para", "detente",
    "envia", "enviale", "envio", "manda", "mandale", "paga", "pasa", "transfiere", "consigna",
    "mil", "pesos", "un",
})


def _check(phrase) -> None:
    if not isinstance(phrase, str):
        raise ValueError("a challenge phrase must be text")
    tokens = words(phrase)
    if not CHALLENGE_MIN_WORDS <= len(tokens) <= CHALLENGE_MAX_WORDS:
        raise ValueError(f"a challenge phrase needs {CHALLENGE_MIN_WORDS} to {CHALLENGE_MAX_WORDS} words")
    if any(c.isdigit() for c in phrase) or set(tokens) & FORBIDDEN_WORDS:
        raise ValueError("a challenge phrase cannot have digits or reserved words")


def load_bank(path: Path | str | None = None) -> list[str]:
    """Lee y valida el banco: al menos 30 frases válidas y distintas. Un banco inválido es error de configuración."""
    data = json.loads(Path(path or CHALLENGE_BANK_PATH).read_text(encoding="utf-8"))
    phrases = data.get("phrases") if isinstance(data, dict) else None
    if not isinstance(phrases, list) or len(phrases) < CHALLENGE_MIN_PHRASES:
        raise ValueError(f"the challenge bank needs at least {CHALLENGE_MIN_PHRASES} phrases")
    for phrase in phrases:
        _check(phrase)
    if len({" ".join(words(p)) for p in phrases}) != len(phrases):
        raise ValueError("the challenge bank has repeated phrases")
    return list(phrases)


def pick_phrase(bank: list[str], used: set[str], rng, last: str | None = None) -> str:
    """Una frase al azar entre las no usadas; si ya se usaron todas, entre todas menos la última."""
    candidates = [p for p in bank if p not in used] or [p for p in bank if p != last]
    if not candidates:
        raise ValueError("the challenge bank is empty")
    return rng.choice(candidates)


def _edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def phrase_match(transcript, expected: str) -> float:
    """1 - errores/palabras (0 a 1), por palabra y sin tildes, mayúsculas ni signos. Entrada que no es texto: 0."""
    wanted = words(expected) if isinstance(expected, str) else []
    if not wanted:
        raise ValueError("the expected phrase cannot be empty")
    heard = words(transcript) if isinstance(transcript, str) else []
    if not heard:
        return 0.0
    return max(0.0, 1 - _edit_distance(heard, wanted) / len(wanted))


def challenge_matches(transcript, expected: str) -> bool:
    return phrase_match(transcript, expected) >= CHALLENGE_MIN_MATCH
