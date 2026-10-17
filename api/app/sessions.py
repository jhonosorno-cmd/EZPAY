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
        self.pending_authorization = False

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

    def take_pending_authorization(self) -> Session | None:
        for session in self._sessions.values():
            if session.pending_authorization and not session.expired():
                session.pending_authorization = False
                return session
        return None
