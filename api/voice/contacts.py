"""contact-resolution: destinatario dicho -> contacto de la agenda, sin adivinar (SEG-4).

La wallet sale solo de la agenda; `options` solo lleva alias y nombre. Exacta normalizada única ->
RESOLVED; varias exactas, coincidencia parcial o aproximada -> CHOICE (nunca se elige sola); nada ->
NOT_FOUND. La agenda del MVP es provisional (`agenda_provisional.json`) y se reemplaza por la de Pagos.
"""
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from voice.replies import Reply, classify_reply
from voice.text import words

AGENDA_KEYS = {"alias", "name", "walletAddress", "previouslyPaid"}
_ALIAS = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# Algo que parece una wallet, un payment pointer, una URL o un correo: nunca se busca en la agenda.
_WALLET_LIKE = re.compile(r"https?:|://|www\.|\$|/|@|\.[a-z]{2,}", re.IGNORECASE)
STOPWORDS = {"a", "al", "de", "del", "el", "la", "las", "los", "mi", "mis", "para", "su", "sus"}
MAX_SPOKEN_CHARS = 100
MAX_OPTIONS = 3


@dataclass(frozen=True)
class Option:
    alias: str
    name: str


@dataclass(frozen=True)
class Contact:
    alias: str
    name: str
    wallet_address: str
    previously_paid: bool

    def option(self) -> Option:
        return Option(self.alias, self.name)


class Kind(str, Enum):
    RESOLVED = "RESOLVED"
    CHOICE = "CHOICE"
    NOT_FOUND = "NOT_FOUND"
    UNCLEAR = "UNCLEAR"


@dataclass(frozen=True)
class Resolution:
    kind: Kind
    contact: Contact | None = None
    options: tuple[Option, ...] = ()


def load_agenda(path: Path | str) -> tuple[Contact, ...]:
    """Lee la agenda (JSON con `contacts`). Una agenda mal formada es un error de configuración."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("contacts") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("agenda must be an object with a 'contacts' list")
    contacts, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != AGENDA_KEYS:
            raise ValueError(f"each contact needs exactly {sorted(AGENDA_KEYS)}")
        alias, name, wallet, paid = row["alias"], row["name"], row["walletAddress"], row["previouslyPaid"]
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias) or alias in seen:
            raise ValueError(f"invalid or duplicated alias {alias!r}")
        if not isinstance(name, str) or not words(name):
            raise ValueError(f"invalid name for {alias!r}")
        if not isinstance(wallet, str) or not wallet.startswith("https://"):
            raise ValueError(f"walletAddress of {alias!r} must start with https://")
        if type(paid) is not bool:
            raise ValueError(f"previouslyPaid of {alias!r} must be true or false")
        seen.add(alias)
        contacts.append(Contact(alias, name, wallet, paid))
    return tuple(contacts)


def _key(text: str) -> str:
    return " ".join(words(text))


def _distance(a: str, b: str) -> int:
    """Distancia de edición (Levenshtein): inserciones, borrados y cambios de una letra."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _near(key: str, contact: Contact) -> int | None:
    """Distancia al contacto si es un parecido aceptable: 1 letra en palabras de 4, 2 desde 5."""
    compact = key.replace(" ", "")
    limit = 0 if len(compact) <= 3 else 1 if len(compact) == 4 else 2
    targets = {_key(contact.alias).replace(" ", ""), _key(contact.name).replace(" ", "")}
    targets |= {w for w in words(contact.alias) + words(contact.name) if len(w) >= 3}
    best = min(_distance(compact, t) for t in targets)
    return best if 0 < best <= limit else None


def _choice(contacts: Sequence[Contact]) -> Resolution:
    return Resolution(Kind.CHOICE, options=tuple(c.option() for c in contacts[:MAX_OPTIONS]))


def resolve_recipient(spoken: str | None, agenda: Sequence[Contact]) -> Resolution:
    """Destinatario dicho -> Resolution. Nunca devuelve un contacto que no esté en `agenda`."""
    if not isinstance(spoken, str) or len(spoken) > MAX_SPOKEN_CHARS or _WALLET_LIKE.search(spoken):
        return Resolution(Kind.NOT_FOUND)
    tokens = words(spoken)
    content = set(tokens) - STOPWORDS
    if not content:
        return Resolution(Kind.NOT_FOUND)
    key = " ".join(tokens)
    exact = [c for c in agenda if key in (_key(c.alias), _key(c.name))]
    if len(exact) == 1:
        return Resolution(Kind.RESOLVED, contact=exact[0])
    if exact:
        return _choice(exact)
    partial = [c for c in agenda if content <= set(words(c.alias)) | set(words(c.name))]
    if partial:
        return _choice(partial)
    near = sorted((d, c.name, i) for i, c in enumerate(agenda) if (d := _near(key, c)) is not None)
    if near:
        return _choice([agenda[i] for _, _, i in near])
    return Resolution(Kind.NOT_FOUND)


def resolve_choice(reply: str | None, offered: Sequence[Option], agenda: Sequence[Contact]) -> Resolution:
    """Elección entre las `offered`: alias o nombre exacto (normalizado), o "sí" si había una sola.
    Cualquier otra respuesta -> UNCLEAR. El contacto (y su wallet) sale siempre de `agenda`."""
    if not offered or not isinstance(reply, str) or len(reply) > MAX_SPOKEN_CHARS:
        return Resolution(Kind.UNCLEAR)
    key = _key(reply)
    hits = [o for o in offered if key and key in (_key(o.alias), _key(o.name))]
    if not hits and len(offered) == 1 and classify_reply(reply) is Reply.YES:
        hits = list(offered)
    if len(hits) != 1:
        return Resolution(Kind.UNCLEAR)
    contact = next((c for c in agenda if c.alias == hits[0].alias), None)
    return Resolution(Kind.RESOLVED, contact=contact) if contact else Resolution(Kind.UNCLEAR)
