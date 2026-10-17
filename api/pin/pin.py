"""Componente de PIN mínimo (spec pin-validation, D5).

- Alta solo por configuración: hash con sal con `hashlib.scrypt`, leído de la
  variable de entorno EZPAY_PIN_HASH con formato
  `scrypt$N$r$p$sal_b64$hash_b64`. Sin endpoint de alta.
- Formato 4–6 dígitos ASCII; formato inválido se rechaza sin invocar el KDF y sin
  consumir intento [DECIDIDO 2026-10-16].
- Comparación en tiempo constante con `hmac.compare_digest` sobre los derivados.
- Contadores: por sesión (3 fallos → sessionFailures >= 3) y global PERSISTIDO
  (H2, tarea 1.4: 5 fallos seguidos entre sesiones → locked). El estado global
  vive en EZPAY_PIN_DATA_DIR (por defecto api/.data/pin/, fuera de git) como
  {"globalFailures": int, "locked": bool}; cada fallo, cada PIN correcto
  (reinicia el global) y cada bloqueo se guardan antes de responder, así que un
  reinicio del backend conserva el bloqueo y el conteo. Archivo corrupto ⇒
  falla cerrado (locked, ver pin/store.py). Un PIN correcto reinicia el
  contador global, NO el de sesión (decisión literal de D5: 3 fallos por
  sesión). Una sesión con 3 fallos deja de validar intentos (defensa en
  profundidad), igual que con el bloqueo global. Las sesiones se memorizan con
  tope (se descarta la más antigua) para que el mapa no crezca sin límite. Los
  contadores, el bloqueo y la escritura del estado se protegen con
  threading.Lock (FastAPI atiende peticiones concurrentes).
- Sin PIN configurado: nunca OK (falla cerrado).
- Privacidad: el PIN no va a logs, ni a `error.message`, ni a `repr`, ni fuera
  de Python; en disco SOLO {globalFailures, locked}, nunca PIN/hash/sesiones.
  El estado es inyectable (PinValidator con hash_provider y data_dir) para que
  las pruebas sean aisladas.
"""
import base64
import binascii
import hashlib
import hmac
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass

from pin.store import PinStore

logger = logging.getLogger(__name__)

PIN_HASH_ENV = "EZPAY_PIN_HASH"
HASH_PREFIX = "scrypt"
MIN_DIGITS = 4
MAX_DIGITS = 6
MAX_SESSION_FAILURES = 3
MAX_GLOBAL_FAILURES = 5
MAX_TRACKED_SESSIONS = 1000
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
_SALT_BYTES = 16


class PinError(RuntimeError):
    """Error operativo del componente; nunca incluye datos del PIN."""


@dataclass(frozen=True)
class PinResult:
    result: str  # "OK" | "WRONG" | "INVALID_FORMAT"
    sessionFailures: int
    remaining: int
    locked: bool


def build_hash_spec(pin: str, salt: bytes | None = None, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> str:
    """Genera `scrypt$N$r$p$sal_b64$hash_b64` para copiar a .env."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(pin.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=SCRYPT_MAXMEM)
    return f"{HASH_PREFIX}${n}${r}${p}${base64.b64encode(salt).decode('ascii')}${base64.b64encode(derived).decode('ascii')}"


def _parse_hash_spec(spec: str) -> tuple[int, int, int, bytes, bytes]:
    parts = spec.split("$")
    if len(parts) != 6 or parts[0] != HASH_PREFIX:
        raise PinError("PIN hash configuration is invalid")
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PinError("PIN hash configuration is invalid") from exc
    if not salt or not expected:
        raise PinError("PIN hash configuration is invalid")
    return n, r, p, salt, expected


def _derive(pin: str, spec: str) -> bytes:
    n, r, p, salt, expected = _parse_hash_spec(spec)
    try:
        derived = hashlib.scrypt(pin.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected), maxmem=SCRYPT_MAXMEM)
    except Exception as exc:
        raise PinError("PIN verification failed") from None
    return derived


def is_valid_pin(pin: str) -> bool:
    """PIN válido: string de 4 a 6 dígitos ASCII. La usan verify y el script de alta."""
    return (
        isinstance(pin, str)
        and pin.isascii()
        and pin.isdigit()
        and MIN_DIGITS <= len(pin) <= MAX_DIGITS
    )


class PinValidator:
    """Estado inyectable del componente: contadores de sesión en memoria del
    proceso y estado global persistido (pin/store.py), todo bajo un lock para
    peticiones concurrentes."""

    def __init__(self, hash_provider=None, data_dir=None):
        if hash_provider is None:
            hash_provider = lambda: os.environ.get(PIN_HASH_ENV) or None  # noqa: E731
        self._hash_provider = hash_provider
        self._lock = threading.Lock()
        self._session_failures: "OrderedDict[str, int]" = OrderedDict()
        self._store = PinStore(data_dir)
        with self._lock:
            # Al iniciar se carga el estado global persistido. Archivo corrupto
            # ⇒ (0, True) por pin/store.py: falla cerrado, el reset lo repara.
            self._global_failures, self._locked = self._store.load()

    def is_configured(self) -> bool:
        return bool(self._hash_provider())

    def _persistir(self) -> None:
        """Guarda el estado global ANTES de responder. Error de disco ⇒ aviso y
        seguir en memoria (no interrumpe la verificación)."""
        try:
            self._store.save(self._global_failures, self._locked)
        except Exception as exc:
            logger.warning("PIN state could not be persisted (%s)", type(exc).__name__)

    def verify(self, pin: str, session_id: str) -> PinResult:
        if not is_valid_pin(pin):
            with self._lock:
                failures = self._session_failures.get(session_id, 0)
                return PinResult("INVALID_FORMAT", failures, max(0, MAX_SESSION_FAILURES - failures), self._locked)

        with self._lock:
            if self._locked:
                failures = self._session_failures.get(session_id, 0)
                return PinResult("WRONG", failures, 0, True)

            failures = self._session_failures.get(session_id, 0)
            if failures >= MAX_SESSION_FAILURES:
                return PinResult("WRONG", failures, 0, self._locked)

            try:
                spec = self._hash_provider()
            except Exception as exc:
                raise PinError("PIN configuration could not be read") from None
            if not spec:
                return self._register_failure(session_id)

            derived = _derive(pin, spec)
            expected = _parse_hash_spec(spec)[4]
            if hmac.compare_digest(derived, expected):
                self._global_failures = 0
                self._persistir()  # el reinicio del global también persiste
                failures = self._session_failures.get(session_id, 0)
                return PinResult("OK", failures, max(0, MAX_SESSION_FAILURES - failures), self._locked)
            return self._register_failure(session_id)

    def _register_failure(self, session_id: str) -> PinResult:
        failures = self._session_failures.get(session_id, 0) + 1
        self._session_failures[session_id] = failures
        self._session_failures.move_to_end(session_id)
        while len(self._session_failures) > MAX_TRACKED_SESSIONS:
            self._session_failures.popitem(last=False)
        self._global_failures += 1
        if self._global_failures >= MAX_GLOBAL_FAILURES:
            self._locked = True
        self._persistir()  # cada fallo y cada bloqueo se guardan antes de responder
        return PinResult("WRONG", failures, max(0, MAX_SESSION_FAILURES - failures), self._locked)

    def reset_lock(self) -> None:
        with self._lock:
            self._locked = False
            self._global_failures = 0
            self._persistir()  # el reset del proceso también escribe el estado persistido


default_validator = PinValidator()


def verify_pin(pin: str, session_id: str) -> PinResult:
    return default_validator.verify(pin, session_id)


def reset_pin_lock() -> None:
    default_validator.reset_lock()