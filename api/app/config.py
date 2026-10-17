"""Configuración del backend, solo desde el entorno (nunca secretos en el código).

Moneda y escala salen de ASSET_CODE / ASSET_SCALE (CONV-1, wallet-handoff): las mismas que usa el
cliente de Node y el frontend (VITE_ASSET_CODE / VITE_ASSET_SCALE).
"""
import os
from dataclasses import dataclass
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _load_dotenv(path: Path) -> None:
    """Carga `api/.env` si existe, sin pisar variables ya definidas. Nunca imprime valores."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    asset_code: str
    asset_scale: int
    node_base_url: str
    user_id: str
    wallet_address: str | None
    finish_uri: str
    agenda_path: Path
    data_dir: Path
    high_amount_value: str | None
    pending_window_seconds: int
    default_budget_value: str
    default_budget_interval: str | None
    cors_origins: tuple[str, ...]
    warmup_local_whisper: bool

    @property
    def high_amount_threshold(self) -> dict | None:
        if not self.high_amount_value:
            return None
        return {"value": self.high_amount_value, "assetCode": self.asset_code, "assetScale": self.asset_scale}


def load_settings() -> Settings:
    _load_dotenv(API_DIR / ".env")
    from voice.config import AGENDA_PATH

    return Settings(
        asset_code=_env("ASSET_CODE", "COP"),
        asset_scale=int(_env("ASSET_SCALE", "2")),
        node_base_url=_env("NODE_BASE_URL", "http://localhost:4000/v1"),
        user_id=_env("EZPAY_USER_ID", "demo-user"),
        # Wallet de la usuaria de la demo (la misma WALLET_ADDRESS de payments/.env).
        wallet_address=_env("EZPAY_WALLET_ADDRESS") or _env("WALLET_ADDRESS"),
        finish_uri=_env("EZPAY_FINISH_URI", "http://localhost:5173/grant-callback"),
        agenda_path=Path(_env("EZPAY_AGENDA_PATH", str(AGENDA_PATH))),
        data_dir=Path(_env("EZPAY_APP_DATA_DIR", str(API_DIR / ".data" / "app"))),
        # 100.000 COP (X-4, 2026-10-17, design.md de add-decision-engine); vacío = desactivado
        high_amount_value=_env("EZPAY_HIGH_AMOUNT_VALUE", "10000000"),
        pending_window_seconds=int(_env("EZPAY_PENDING_WINDOW_SECONDS", "120")),
        # Presupuesto que se pide cuando un comando llega sin grant (SEG-1): 200.000 COP
        default_budget_value=_env("EZPAY_DEFAULT_BUDGET_VALUE", "20000000"),
        default_budget_interval=_env("EZPAY_DEFAULT_BUDGET_INTERVAL"),
        cors_origins=tuple(_env("EZPAY_CORS_ORIGINS", "http://localhost:5173").split(",")),
        warmup_local_whisper=_env("EZPAY_WARMUP_WHISPER", "1") == "1",
    )
