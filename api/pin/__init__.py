"""Componente de PIN mínimo (ML 2, hito H1).

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

__all__ = [
    "PIN_HASH_ENV",
    "PinError",
    "PinResult",
    "PinValidator",
    "build_hash_spec",
    "is_valid_pin",
    "reset_pin_lock",
    "verify_pin",
]