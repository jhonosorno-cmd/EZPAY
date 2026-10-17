"""Dobles para las pruebas de api/app: Node (Contrato A), voz y PIN. Datos inventados."""
import copy
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import yaml

from app.config import load_settings
from app.contacts import ContactError, ContactBook, WalletInfo
from app.orchestrator import Orchestrator
from app.voice_io import VoiceIO
from payments_client import PaymentPending, PaymentsError
from pin import PinResult
from voice.transcribe import Engine, Transcript

ROOT = Path(__file__).resolve().parents[3]

AGENDA = {
    "contacts": [
        {"alias": "mi-hija", "name": "Laura hija", "walletAddress": "https://wallet.test/laura-hija", "previouslyPaid": True},
        {"alias": "laura-vecina", "name": "Laura vecina", "walletAddress": "https://wallet.test/laura-vecina", "previouslyPaid": False},
        {"alias": "jose", "name": "José", "walletAddress": "https://wallet.test/jose", "previouslyPaid": False},
    ]
}


def amt(value: str) -> dict:
    return {"value": value, "assetCode": "COP", "assetScale": 2}


class FakeResolver:
    """Open Payments falso para las wallet addresses: /usd está en USD y /nadie no existe."""

    def __init__(self):
        self.calls = []

    def resolve(self, url):
        self.calls.append(url)
        if url.endswith("/nadie"):
            raise ContactError(400, "INVALID_WALLET", "No pude encontrar esa billetera")
        code = "USD" if url.endswith("/usd") else "COP"
        return WalletInfo(url, url.rsplit("/", 1)[-1].capitalize(), code, 2)


class FakePayments:
    """Node falso: registra las llamadas y responde con las formas del Contrato A."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.grants: dict[str, dict] = {}
        self.fee = "15000"
        self.exceeds = lambda grant_id, receive: False
        self.payment_status = "COMPLETED"
        self.payment_pending = False
        self.payments: dict[str, dict] = {}
        self.invalid: set[str] = set()
        self._n = 0

    def _id(self, prefix):
        self._n += 1
        return f"{prefix}_{self._n}"

    def create_grant(self, user_id, wallet_address, finish_uri, debit_value, interval=None, request_id=None):
        gid = self._id("g")
        limit = {"debitAmount": amt(debit_value)}
        if interval:
            limit["interval"] = interval
        self.grants[gid] = {"grantId": gid, "status": "PENDING", "limit": limit}
        self.calls.append(("create_grant", debit_value, interval))
        return {"grantId": gid, "status": "PENDING", "interactUrl": f"https://wallet.test/interact/{gid}"}

    def continue_grant(self, grant_id, interact_ref, hash_value, request_id=None):
        self.calls.append(("continue_grant", grant_id, interact_ref, hash_value))
        grant = self.grants[grant_id]
        grant["status"] = "ACTIVE"
        return {"grantId": grant_id, "status": "ACTIVE", "limit": grant["limit"], "remaining": grant["limit"]["debitAmount"]}

    def get_grant(self, grant_id, request_id=None):
        self.calls.append(("get_grant", grant_id))
        if grant_id not in self.grants:
            raise PaymentsError(404, "GRANT_NOT_FOUND")
        grant = self.grants[grant_id]
        return {"grantId": grant_id, "status": grant["status"], "limit": grant["limit"], "spent": amt("0"),
                "remaining": grant.get("remaining", grant["limit"]["debitAmount"])}

    def cancel_grant(self, grant_id, request_id=None):
        self.calls.append(("cancel_grant", grant_id))

    def create_quote(self, grant_id, receiver, receive_value, request_id=None):
        self.calls.append(("create_quote", grant_id, receiver, receive_value))
        if grant_id in self.invalid:
            raise PaymentsError(401, "GRANT_INVALID")
        debit = str(int(receive_value) + int(self.fee))
        return {"quoteId": self._id("q"), "debitAmount": amt(debit), "receiveAmount": amt(receive_value),
                "expiresAt": "2026-10-17T12:00:00Z", "exceedsRemaining": self.exceeds(grant_id, receive_value)}

    def create_payment(self, quote_id, idempotency_key, request_id=None):
        self.calls.append(("create_payment", quote_id, idempotency_key))
        if self.payment_pending:
            return PaymentPending(payment_id=None)
        pid = self._id("p")
        self.payments[pid] = {"paymentId": pid, "status": self.payment_status, "debitAmount": amt("2015000"),
                              "sentAmount": amt("2000000")}
        return copy.deepcopy(self.payments[pid])

    def get_payment(self, payment_id, request_id=None):
        self.calls.append(("get_payment", payment_id))
        return {"paymentId": payment_id, "status": self.payments[payment_id]["status"], "sentAmount": amt("2000000")}

    def wait_for_payment(self, payment_id, request_id=None, **_kw):
        return self.get_payment(payment_id)

    def names(self):
        return [c[0] for c in self.calls]


class FakeEnrollment:
    def enroll(self, samples, consent):
        return {"enrolled": True}


class FakeVoice(VoiceIO):
    """Voz falsa: el "audio" es el texto dicho en UTF-8; la verificación es configurable."""

    def __init__(self):
        super().__init__(enrollment=FakeEnrollment())
        self.voice_status = "VERIFIED"
        self.is_enrolled = True
        self.transcribed = 0

    def load(self, warmup_local=False):
        pass

    def enrolled(self):
        return self.is_enrolled

    @property
    def speaker_ready(self):
        return True

    def decode(self, audio):
        return audio

    def transcribe_command(self, audio, request_id, verify):
        self.transcribed += 1
        text = audio.decode("utf-8")
        voice = {"status": self.voice_status, "score": 0.7 if self.voice_status == "VERIFIED" else 0.2}
        return Transcript(text, bool(text.strip()), Engine.LOCAL), voice if verify else {"status": "NOT_AVAILABLE", "score": None}


class FakePin:
    """Componente de PIN falso con la misma forma de PinResult; el PIN correcto es 4826."""

    def __init__(self):
        self.failures: dict[str, int] = {}

    def __call__(self, pin, session_id):
        if not pin.isdigit() or not 4 <= len(pin) <= 6:
            return PinResult("INVALID_FORMAT", self.failures.get(session_id, 0), 3, False)
        if pin == "4826":
            return PinResult("OK", self.failures.get(session_id, 0), 3, False)
        n = self.failures.get(session_id, 0) + 1
        self.failures[session_id] = n
        return PinResult("WRONG", n, max(0, 3 - n), False)


def build(tmp: Path):
    agenda = tmp / "agenda.json"
    agenda.write_text(json.dumps(AGENDA), encoding="utf-8")
    settings = replace(load_settings(), agenda_path=agenda, data_dir=tmp / "app", wallet_address="https://wallet.test/marta",
                       asset_code="COP", asset_scale=2, warmup_local_whisper=False)
    payments, voice, pin = FakePayments(), FakeVoice(), FakePin()
    contacts = ContactBook(tmp / "app" / "contacts.json", FakeResolver(), "COP", 2, settings.wallet_address, agenda)
    orch = Orchestrator(settings, payments, voice, pin_verifier=pin, contacts=contacts)
    return orch, payments, voice, pin


# --------------------------------------------------------- esquemas del contrato
def _load_yaml(name):
    return yaml.safe_load((ROOT / "openapi" / name).read_text(encoding="utf-8"))


def _to_jsonschema(node, contract, components):
    if isinstance(node, list):
        return [_to_jsonschema(n, contract, components) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = node["$ref"]
        doc = components if ref.startswith("components.yaml") else contract
        target = doc
        for part in ref.split("#/")[1].split("/"):
            target = target[part]
        return _to_jsonschema(target, contract, components)
    out = {k: _to_jsonschema(v, contract, components) for k, v in node.items()
           if not k.startswith("x-") and k not in ("example", "examples", "nullable", "description", "format")}
    if node.get("nullable"):
        out = {"anyOf": [out, {"type": "null"}]}
    return out


def contract_schema(name: str) -> dict:
    contract, components = _load_yaml("contract-b.yaml"), _load_yaml("components.yaml")
    return _to_jsonschema(contract["components"]["schemas"][name], contract, components)


def temp_dir():
    return tempfile.TemporaryDirectory()


class DoubleAppMixin:
    """setUp común: la app real (orquestador) con Node, voz y PIN falsos."""

    def setUp(self):
        from fastapi.testclient import TestClient

        from app.main import create_app
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch, self.node, self.voice, self.pin = build(Path(self._tmp.name))
        self.app = create_app(orchestrator=self.orch, voice_io=self.voice)
        self.client = TestClient(self.app)

    def reach_pin(self):
        """Lleva una sesión a AWAITING_PIN por el camino real: presupuesto aprobado y comando por texto."""
        self.client.post("/api/budget", json={"debitAmount": amt("20000000")})
        self.client.post("/api/grant-callback", json={"interactRef": "ref-inventada", "hash": "hash-inventado"})
        first = self.client.post("/api/turns", data={"text": "envíale veinte mil a mi hija"}).json()
        assert first["state"] == "AWAITING_PIN", first
        return first
