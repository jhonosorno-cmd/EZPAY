"""Configuración del backend: moneda de la demo (CONV-1), TTL de sesión, CORS y logger.

La moneda y la escala SOLO del entorno (ASSET_CODE, ASSET_SCALE): sin constantes de
moneda en el código. El default COP/2 es solo para el arranque local.
"""
import os

SESSION_TTL_SECONDS = 15 * 60
CORS_ORIGIN = "http://localhost:5173"
LOG_NAME = "api.app"
PLACEHOLDER_INTERACT_URL = "https://auth.interledger-test.dev/interact/example"


def asset_code() -> str:
    return os.environ.get("ASSET_CODE", "COP")


def asset_scale() -> int:
    raw = os.environ.get("ASSET_SCALE")
    return int(raw) if raw is not None else 2