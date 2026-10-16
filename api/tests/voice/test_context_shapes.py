"""Forma de lo que Voz entrega al orquestador y al motor: los nombres exactos del `context` de
`decide(context)` (openspec/changes/add-decision-engine/design.md, rama de ML 2) y de los esquemas
`Amount` (openapi/components.yaml) y `options` (openapi/contract-b.yaml)."""
import json
import re

import pytest

from voice.config import AGENDA_PATH, ASSET
from voice.contacts import Contact, Kind, Option, Resolution, load_agenda, resolve_choice, resolve_recipient
from voice.intents import extract_intent
from voice.replies import classify_reply

AGENDA = load_agenda(AGENDA_PATH)
AMOUNT_KEYS = {"value", "assetCode", "assetScale"}             # components.yaml: additionalProperties false


def assert_amount(d):
    assert set(d) == AMOUNT_KEYS
    assert re.fullmatch(r"[0-9]+", d["value"]) and type(d["assetScale"]) is int and d["assetScale"] >= 0


# --- intent
def test_intent_pago_completo():
    assert extract_intent("Envíale veinte mil a mi hija", ASSET).to_dict() == {
        "action": "PAY",
        "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
        "amountError": None,
        "recipient": "mi hija",
        "status": "OK",
    }


def test_intent_con_error_de_monto():
    d = extract_intent("Envíale 10,505 a Laura", ASSET).to_dict()
    assert d["amount"] is None and d["amountError"] == "TOO_MANY_DECIMALS" and d["status"] == "UNCLEAR"


@pytest.mark.parametrize("text", [
    "Envíale veinte mil a mi hija", "Cancela", "Hola", "Envíale plata a mi hija", "Envíale 10.50 a Laura",
    "Envíale veinte mil y treinta mil a Laura", "", None,
])
def test_intent_siempre_con_las_cinco_claves_y_valores_del_contrato(text):
    d = extract_intent(text, ASSET).to_dict()
    assert list(d) == ["action", "amount", "amountError", "recipient", "status"]
    assert d["action"] in {"PAY", "CANCEL", "UNKNOWN"}
    assert d["status"] in {"OK", "AMBIGUOUS", "UNCLEAR"}
    assert d["amountError"] in {None, "TOO_MANY_DECIMALS", "AMBIGUOUS_AMOUNT", "INVALID_AMOUNT"}
    if d["amount"] is not None:
        assert_amount(d["amount"])
    json.dumps(d)                                               # serializable sin conversiones


# --- resolution
def test_resolution_resolved():
    assert resolve_recipient("mi hija", AGENDA).to_dict() == {
        "kind": "RESOLVED",
        "contact": {"alias": "mi-hija", "name": "Laura hija",
                    "walletAddress": "https://ilp.interledger-test.dev/ezpay-placeholder-laura-hija",
                    "previouslyPaid": True},
    }


def test_resolution_choice_solo_alias_y_nombre():
    d = resolve_recipient("Laura", AGENDA).to_dict()
    assert d == {"kind": "CHOICE", "options": [{"alias": "mi-hija", "name": "Laura hija"},
                                               {"alias": "laura-vecina", "name": "Laura vecina"}]}
    assert "walletAddress" not in json.dumps(d) and "http" not in json.dumps(d)


def test_resolution_not_found_y_unclear():
    assert resolve_recipient("Pedro", AGENDA).to_dict() == {"kind": "NOT_FOUND"}
    offered = (Option("mi-hija", "Laura hija"),)
    assert resolve_choice("José", offered, AGENDA).to_dict() == {"kind": "UNCLEAR"}


def test_option_to_dict():
    assert Option("jose", "José").to_dict() == {"alias": "jose", "name": "José"}


def test_contact_to_dict_claves_del_motor():
    c = Contact("jose", "José", "https://ilp.interledger-test.dev/ezpay-placeholder-jose", False)
    assert list(c.to_dict()) == ["alias", "name", "walletAddress", "previouslyPaid"]


def test_resolution_kinds_del_motor():
    kinds = {resolve_recipient(t, AGENDA).to_dict()["kind"] for t in ("mi hija", "Laura", "Pedro")}
    assert kinds == {"RESOLVED", "CHOICE", "NOT_FOUND"}
    assert Resolution(Kind.NOT_FOUND).to_dict() == {"kind": "NOT_FOUND"}


# --- reply
@pytest.mark.parametrize("text,value", [("sí", "YES"), ("no", "NO"), ("eh", "UNCLEAR")])
def test_reply_es_el_texto_del_contrato(text, value):
    assert classify_reply(text).value == value
    assert json.dumps(classify_reply(text)) == f'"{value}"'
