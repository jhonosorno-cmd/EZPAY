"""Agenda de contactos de la usuaria (SEG-4): la única fuente de wallets a las que se puede pagar.

Cada contacto se valida contra Open Payments al guardarse: se consulta la wallet address (GET
público, sin llaves, `Accept: application/json`) y se exige que exista y que esté en la moneda
de la demo (ASSET_CODE/ASSET_SCALE), porque el monto dicho se cotiza como `receiveAmount` en
esa moneda. La agenda se persiste en `EZPAY_APP_DATA_DIR/contacts.json` (fuera de git): solo
alias, nombre y wallet, nada biométrico ni secreto.

La voz resuelve el destinatario solo contra esta agenda (`voice.contacts.resolve_recipient`); el
orquestador la lee en cada turno, así que un contacto nuevo se puede usar de inmediato.
"""
import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import httpx

from voice.contacts import Contact, load_agenda
from voice.text import fold, words

logger = logging.getLogger("ezpay.contacts")

MAX_CONTACTS = 50
MAX_NAME_CHARS = 40
_ALIAS_CLEAN = re.compile(r"[^a-z0-9]+")
_HOST_PATH = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}(:[0-9]+)?(/[A-Za-z0-9._~-]+)+/?$", re.IGNORECASE)


class ContactError(Exception):
    """Error de la agenda con el código del Contrato B (extensión `x-proposed`)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WalletInfo:
    id: str
    public_name: str | None
    asset_code: str
    asset_scale: int


def normalize_wallet(raw: str) -> str:
    """`$ilp.interledger-test.dev/laura`, `ilp.interledger-test.dev/laura` o la URL https → URL https."""
    if not isinstance(raw, str):
        raise ContactError(400, "INVALID_WALLET", "La dirección de la billetera no es válida")
    value = raw.strip()
    if value.startswith("$"):
        value = value[1:]
    if value.lower().startswith("https://"):
        value = value[8:]
    elif "://" in value:
        raise ContactError(400, "INVALID_WALLET", "La dirección de la billetera debe usar https")
    if not _HOST_PATH.fullmatch(value):
        raise ContactError(400, "INVALID_WALLET", "La dirección de la billetera no es válida")
    return "https://" + value.rstrip("/")


class WalletResolver:
    """Consulta pública de una wallet address de Open Payments."""

    def __init__(self, http: httpx.Client | None = None, timeout: float = 6.0):
        self._http = http or httpx.Client(timeout=timeout, follow_redirects=False)

    def resolve(self, url: str) -> WalletInfo:
        try:
            res = self._http.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError:
            raise ContactError(400, "INVALID_WALLET", "No pude encontrar esa billetera") from None
        if res.status_code != 200:
            raise ContactError(400, "INVALID_WALLET", "No pude encontrar esa billetera")
        try:
            data = res.json()
        except ValueError:
            raise ContactError(400, "INVALID_WALLET", "No pude encontrar esa billetera") from None
        ok = (isinstance(data, dict) and isinstance(data.get("id"), str) and isinstance(data.get("assetCode"), str)
              and isinstance(data.get("assetScale"), int) and isinstance(data.get("authServer"), str)
              and isinstance(data.get("resourceServer"), str))
        if not ok:
            raise ContactError(400, "INVALID_WALLET", "Esa dirección no es una billetera de Open Payments")
        name = data.get("publicName") if isinstance(data.get("publicName"), str) else None
        return WalletInfo(data["id"].rstrip("/"), name, data["assetCode"], data["assetScale"])


def _alias_for(name: str) -> str:
    return _ALIAS_CLEAN.sub("-", fold(name)).strip("-")


class ContactBook:
    def __init__(self, path: Path, resolver: WalletResolver, asset_code: str, asset_scale: int,
                 own_wallet: str | None, seed_path: Path | None = None):
        self._path = Path(path)
        self._resolver = resolver
        self._asset = (asset_code, asset_scale)
        self._own = own_wallet.rstrip("/") if own_wallet else None
        self._lock = threading.Lock()
        self._rows: list[dict] = self._load(seed_path)

    # ------------------------------------------------------------- lectura
    def _load(self, seed_path) -> list[dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            rows = data.get("contacts", []) if isinstance(data, dict) else []
            return [r for r in rows if isinstance(r, dict) and {"alias", "name", "walletAddress"} <= set(r)]
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            logger.warning("Contacts file unreadable; starting with an empty agenda")
            return []
        if seed_path is not None and Path(seed_path).is_file():
            # previouslyPaid solo desde la semilla (preparación de la demo, D9); nunca desde la web.
            return [{"alias": c.alias, "name": c.name, "walletAddress": c.wallet_address,
                     "previouslyPaid": c.previously_paid}
                    for c in load_agenda(seed_path) if "ezpay-placeholder" not in c.wallet_address]
        return []

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._rows]

    def agenda(self) -> tuple[Contact, ...]:
        """Contactos en la forma de `voice.contacts` (previouslyPaid lo completa el historial)."""
        with self._lock:
            return tuple(Contact(r["alias"], r["name"], r["walletAddress"], r.get("previouslyPaid") is True)
                         for r in self._rows)

    # ------------------------------------------------------------- escritura
    def add(self, name, wallet) -> dict:
        if not isinstance(name, str) or not words(name) or len(name.strip()) > MAX_NAME_CHARS \
                or not all(w.isalpha() for w in words(name)):
            raise ContactError(400, "INVALID_CONTACT", "El nombre debe tener solo letras (máximo 40)")
        name = " ".join(name.split())
        url = normalize_wallet(wallet)
        alias = _alias_for(name)
        with self._lock:
            if len(self._rows) >= MAX_CONTACTS:
                raise ContactError(400, "INVALID_CONTACT", "La agenda está llena")
            if any(r["alias"] == alias for r in self._rows):
                raise ContactError(409, "CONTACT_EXISTS", "Ya tienes un contacto con ese nombre")
            if any(r["walletAddress"] == url for r in self._rows):
                raise ContactError(409, "CONTACT_EXISTS", "Ya tienes un contacto con esa billetera")
        if self._own and url == self._own:
            raise ContactError(400, "INVALID_WALLET", "Esa es tu propia billetera")
        info = self._resolver.resolve(url)  # fuera del candado: es una llamada de red
        if (info.asset_code, info.asset_scale) != self._asset:
            raise ContactError(400, "INVALID_WALLET",
                               f"La billetera debe estar en {self._asset[0]}; esta está en {info.asset_code}")
        row = {"alias": alias, "name": name, "walletAddress": info.id or url, "publicName": info.public_name,
               "assetCode": info.asset_code}
        with self._lock:
            if any(r["alias"] == alias or r["walletAddress"] == row["walletAddress"] for r in self._rows):
                raise ContactError(409, "CONTACT_EXISTS", "Ya tienes ese contacto")
            self._rows.append(row)
            self._save()
        logger.info("Contact added alias=%s", alias)
        return dict(row)

    def remove(self, alias: str) -> None:
        with self._lock:
            before = len(self._rows)
            self._rows = [r for r in self._rows if r["alias"] != alias]
            if len(self._rows) == before:
                raise ContactError(404, "CONTACT_NOT_FOUND", "Ese contacto no existe")
            self._save()

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            ignore = self._path.parent / ".gitignore"  # la agenda nunca va al repo público
            if not ignore.exists():
                ignore.write_text("*\n", encoding="utf-8")
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"contacts": self._rows}, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as exc:
            logger.warning("Contacts could not be persisted (%s)", type(exc).__name__)
