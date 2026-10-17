"""Almacén de sesiones en memoria: crear, leer, expirar.

Las sesiones NUNCA guardan el PIN, el audio ni el texto del usuario: solo el estado
del turno y datos no sensibles. Expiración perezosa por TTL.
"""
import time
import uuid

from .config import SESSION_TTL_SECONDS
from .states import TurnState


class SessionNotFound(Exception):
    pass


class Session:
    def __init__(self, session_id: str):
        self.id = session_id
        self.created_at = time.monotonic()
        self.state = TurnState.AWAITING_COMMAND
        self.pending_authorization: str | None = None  # "budget" | "one_off"
        self.grant_id: str | None = None  # el grant esperando callback; NUNCA tokens
        self.intent: dict | None = None  # intención pendiente entre turnos
        self.contact: dict | None = None  # contacto resuelto (alias, nombre, wallet)
        self.quote: dict | None = None  # quote del cliente entre turnos
        self.options: list | None = None  # opciones de elección de destinatario
        self.voice: dict | None = None  # resultado de la verificación del comando (D4)
        self.enrolled: bool = False
        self.unclear_replies: int = 0
        self.idempotency_key: str | None = None  # una clave por quote (reintentos la reutilizan)
        self.payment_id: str | None = None
        self.pending_payment: dict | None = None  # pago sin resolver: recipient/createdAt/status/...

    def expired(self) -> bool:
        return time.monotonic() - self.created_at > SESSION_TTL_SECONDS

    def __repr__(self) -> str:  # nunca incluye contenido del usuario
        return f"Session(id={self.id!r}, state={self.state.value})"


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session("s_" + uuid.uuid4().hex[:12])
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None or session.expired():
            self._sessions.pop(session_id, None)
            raise SessionNotFound(session_id)
        return session

    def set_pending_authorization(self, session: Session) -> None:
        session.pending_authorization = True

    def take_pending_authorization(self, grant_id: str | None = None) -> Session | None:
        """La sesión pendiente de autorización en la wallet.

        El callback del frontend no lleva identificadores del grant: si el cuerpo
        trae un `grantId` reenviado se busca por él; si no, solo hay UNA sesión
        pendiente posible (demo de una usuaria). Sin pendientes o con varias
        ambiguas devuelve None y el turno responde con sessionId 'unknown' (D-2).
        """
        pending = [s for s in self._sessions.values() if s.pending_authorization and not s.expired()]
        if grant_id:
            matches = [s for s in pending if s.grant_id == grant_id]
            if matches:
                return matches[0]
        return pending[0] if len(pending) == 1 else None
