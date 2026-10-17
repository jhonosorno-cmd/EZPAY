"""Normalización de texto compartida por el módulo de voz: minúsculas y sin tildes."""
import re
import unicodedata


def fold(text: str) -> str:
    """Minúsculas y sin marcas diacríticas ("José" -> "jose", "Sí" -> "si")."""
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def words(text: str) -> list[str]:
    """Palabras ASCII de `text`; todo lo demás (puntuación, guiones, caracteres raros) separa."""
    return re.sub(r"[^a-z0-9]+", " ", fold(text)).split()
