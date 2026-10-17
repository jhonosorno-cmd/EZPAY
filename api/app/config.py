"""Configuración del esqueleto: moneda de la demo (CONV-1), TTL de sesión, CORS y logger."""
ASSET_CODE = "COP"
ASSET_SCALE = 2
SESSION_TTL_SECONDS = 15 * 60
CORS_ORIGIN = "http://localhost:5173"
LOG_NAME = "api.app"
PLACEHOLDER_INTERACT_URL = "https://auth.interledger-test.dev/interact/example"
