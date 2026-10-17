"""Estado del backend: sesiones de conversación (memoria) y estado de la wallet (disco).

Las sesiones viven solo en memoria: nunca guardan audio, transcripciones ni el PIN. El estado de
la wallet (id del grant de presupuesto, historial de destinatarios pagados) se persiste en
`EZPAY_APP_DATA_DIR` (por defecto `api/.data/app/`, fuera de git) para sobrevivir un reinicio:
son solo ids de Node y alias de la agenda, ningún secreto ni dato biométrico.
"""
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger("ezpay.state")

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 500


class TurnState(str, Enum):
    AWAITING_COMMAND = "AWAITING_COMMAND"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_PIN = "AWAITING_PIN"
    AWAITING_RECIPIENT_CHOICE = "AWAITING_RECIPIENT_CHOICE"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


@dataclass
class Command:
    """La intención en curso de la sesión: lo que el motor necesita entre turnos."""
    intent: dict                      # forma `intent` del context (camelCase)
    voice: dict                       # resultado de la verificación del COMANDO (D4)
    transcript_confidence: float | None = None
    resolution: object | None = None  # voice.contacts.Resolution
    quote: dict | None = None         # Quote del Contrato A
    quote_grant_id: str | None = None
    idempotency_key: str | None = None
    unclear_replies: int = 0
    pin_ok: bool = False


@dataclass
class Session:
    id: str
    state: TurnState = TurnState.AWAITING_COMMAND
    command: Command | None = None
    options: tuple = ()               # voice.contacts.Option ofrecidas en AWAITING_RECIPIENT_CHOICE
    touched: float = field(default_factory=time.monotonic)

    def reset_command(self) -> None:
        self.command = None
        self.options = ()


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        with self._lock:
            self._expire()
            session = Session(id=f"s_{uuid.uuid4().hex[:16]}")
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            self._expire()
            session = self._sessions.get(session_id)
            if session is not None:
                session.touched = time.monotonic()
            return session

    def _expire(self) -> None:
        now = time.monotonic()
        for sid in [s for s, v in self._sessions.items() if now - v.touched > SESSION_TTL_SECONDS]:
            del self._sessions[sid]
        while len(self._sessions) > MAX_SESSIONS:
            oldest = min(self._sessions.values(), key=lambda s: s.touched)
            del self._sessions[oldest.id]


@dataclass
class PendingAuth:
    """Un grant esperando la aprobación en la wallet (presupuesto o puntual del exceso)."""
    kind: str                         # "budget" | "excess"
    grant_id: str
    session_id: str | None


@dataclass
class PendingPayment:
    """Pago en PAYMENT_PENDING: lo que hace falta para verificarlo o reintentarlo (misma clave)."""
    session_id: str
    payment_id: str | None
    quote_id: str
    idempotency_key: str
    receiver: str
    contact_name: str
    receive_amount: dict
    debit_amount: dict
    created_at: str
    one_off_grant_id: str | None = None
    alias: str | None = None


class WalletState:
    """Estado de un solo usuario (MVP): grant de presupuesto, autorización y pago pendientes."""

    def __init__(self, data_dir: Path):
        self._file = Path(data_dir) / "state.json"
        self.budget_grant_id: str | None = None
        self.paid_aliases: set[str] = set()
        self.pending_auth: PendingAuth | None = None
        self.pending_payment: PendingPayment | None = None
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            logger.warning("App state file unreadable; starting clean")
            return
        grant = data.get("budgetGrantId")
        self.budget_grant_id = grant if isinstance(grant, str) else None
        paid = data.get("paidAliases")
        self.paid_aliases = {a for a in paid if isinstance(a, str)} if isinstance(paid, list) else set()

    def save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            ignore = self._file.parent.parent / ".gitignore"
            if not ignore.exists():
                ignore.write_text("*\n", encoding="utf-8")
            tmp = self._file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"budgetGrantId": self.budget_grant_id,
                                       "paidAliases": sorted(self.paid_aliases)}), encoding="utf-8")
            tmp.replace(self._file)
        except OSError as exc:
            logger.warning("App state could not be persisted (%s)", type(exc).__name__)
