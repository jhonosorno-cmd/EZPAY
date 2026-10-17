"""Componente de PIN mínimo (ML 2). H2: el estado global (contador de fallos
y bloqueo) se persiste en EZPAY_PIN_DATA_DIR.

Expone `verify_pin(pin, session_id) -> PinResult` y `reset_pin_lock()`,
más el generador de hash `build_hash_spec` que usa el script de alta.
"""
from .pin import (
    PIN_HASH_ENV,
    PinError,
    PinResult,
    PinValidator,
    build_hash_spec,
    is_valid_pin,
    reset_pin_lock,
    verify_pin,
)
from .store import PinStore

__all__ = [
    "PIN_HASH_ENV",
    "PinError",
    "PinResult",
    "PinStore",
    "PinValidator",
    "build_hash_spec",
    "is_valid_pin",
    "reset_pin_lock",
    "verify_pin",
]