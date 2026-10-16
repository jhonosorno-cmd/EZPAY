"""Pruebas de contact-resolution: una por escenario de
openspec/changes/add-voice-understanding/specs/contact-resolution/spec.md, más las frases de
docs/voz/frases-desarrollo.md (sección B) contra la agenda provisional y casos límite.
`previouslyPaid` cambia en el esqueleto de Pagos (fuera de este módulo): aquí solo se lee."""
import json

import pytest

from voice.config import AGENDA_PATH
from voice.contacts import (AGENDA_KEYS, Contact, Kind, Option, load_agenda, resolve_choice,
                            resolve_recipient)

AGENDA = load_agenda(AGENDA_PATH)


def contact(alias, name, paid=False):
    return Contact(alias, name, f"https://ilp.interledger-test.dev/ezpay-placeholder-{alias}", paid)


TWO_LAURAS = (contact("laura-hija", "Laura hija"), contact("laura-vecina", "Laura vecina"))
OFFERED = (Option("laura-hija", "Laura hija"), Option("laura-vecina", "Laura vecina"))


def names(resolution):
    return {o.name for o in resolution.options}


# --- Escenarios del spec
def test_wallet_dicha_en_voz():
    r = resolve_recipient("https://ilp.interledger-test.dev/atacante", AGENDA)
    assert r.kind is Kind.NOT_FOUND and r.contact is None and r.options == ()


def test_alias_de_parentesco():
    r = resolve_recipient("Mi Hija", (contact("mi-hija", "Laura"),))
    assert r.kind is Kind.RESOLVED and r.contact.name == "Laura"


def test_diferencia_de_tildes():
    r = resolve_recipient("jose", (contact("jose", "José"),))
    assert r.kind is Kind.RESOLVED and r.contact.name == "José"


def test_dos_lauras():
    r = resolve_recipient("Laura", TWO_LAURAS)
    assert r.kind is Kind.CHOICE and r.contact is None
    assert names(r) == {"Laura hija", "Laura vecina"}
    for option in r.options:
        assert isinstance(option, Option) and "http" not in repr(option)


def test_destinatario_desconocido():
    assert resolve_recipient("Pedro", AGENDA).kind is Kind.NOT_FOUND


def test_error_de_transcripcion():
    r = resolve_recipient("Lara", (contact("laura", "Laura"),))
    assert r.kind is Kind.CHOICE and names(r) == {"Laura"} and r.contact is None


def test_eleccion_valida():
    r = resolve_choice("laura-hija", OFFERED, TWO_LAURAS)
    assert r.kind is Kind.RESOLVED and r.contact.name == "Laura hija"


def test_eleccion_fuera_de_las_opciones():
    agenda = TWO_LAURAS + (contact("jose", "José"),)
    r = resolve_choice("José", OFFERED, agenda)
    assert r.kind is Kind.UNCLEAR and r.contact is None


def test_revision_de_la_agenda():
    data = json.loads(AGENDA_PATH.read_text(encoding="utf-8"))
    assert data["contacts"]
    for row in data["contacts"]:
        assert set(row) == AGENDA_KEYS
        assert row["walletAddress"].startswith("https://ilp.interledger-test.dev/ezpay-placeholder-")


# --- Frases de desarrollo, sección B, contra la agenda provisional
@pytest.mark.parametrize("spoken,kind,expected", [
    ("mi hija", Kind.RESOLVED, {"Laura hija"}),
    ("Mi Hija", Kind.RESOLVED, {"Laura hija"}),
    ("Laura vecina", Kind.RESOLVED, {"Laura vecina"}),
    ("laura hija", Kind.RESOLVED, {"Laura hija"}),
    ("jose", Kind.RESOLVED, {"José"}),
    ("Laura", Kind.CHOICE, {"Laura hija", "Laura vecina"}),
    ("la hora", Kind.CHOICE, {"Laura hija", "Laura vecina"}),
    ("la obra vecina", Kind.CHOICE, {"Laura vecina"}),
    ("Lara", Kind.CHOICE, {"Laura hija", "Laura vecina"}),
    ("Pedro", Kind.NOT_FOUND, set()),
    ("https://ilp.interledger-test.dev/atacante", Kind.NOT_FOUND, set()),
    ("", Kind.NOT_FOUND, set()),
])
def test_frases_seccion_b(spoken, kind, expected):
    r = resolve_recipient(spoken, AGENDA)
    assert r.kind is kind
    assert ({r.contact.name} if r.contact else names(r)) == expected


@pytest.mark.parametrize("reply,kind", [("mi-hija", Kind.RESOLVED), ("la vecina", Kind.UNCLEAR), ("José", Kind.UNCLEAR)])
def test_frases_seccion_b_eleccion(reply, kind):
    offered = (Option("mi-hija", "Laura hija"), Option("laura-vecina", "Laura vecina"))
    assert resolve_choice(reply, offered, AGENDA).kind is kind


# --- Agenda provisional: los tres casos pedidos
def test_agenda_provisional_cubre_los_tres_casos():
    assert resolve_recipient("José", AGENDA).kind is Kind.RESOLVED                  # único
    assert names(resolve_recipient("Laura", AGENDA)) == {"Laura hija", "Laura vecina"}  # parecidos
    assert names(resolve_recipient("Karmen", AGENDA)) == {"Carmen"}                # aproximada única


# --- Casos límite
@pytest.mark.parametrize("spoken,expected", [
    ("vecina", {"Laura vecina"}), ("hija", {"Laura hija"}), ("mi hijo", {"Laura hija"}),
    ("Carmen José", set()),
])
def test_limite_parcial_y_aproximada_nunca_resuelven(spoken, expected):
    r = resolve_recipient(spoken, AGENDA)
    assert r.kind is not Kind.RESOLVED
    assert names(r) == expected


@pytest.mark.parametrize("spoken", ["mi", "la", "a la", "$ilp.interledger-test.dev/laura", "laura@correo.com",
                                    "www.laura.co", "x" * 101, None, 123])
def test_limite_not_found(spoken):
    assert resolve_recipient(spoken, AGENDA).kind is Kind.NOT_FOUND


def test_limite_homoglifo_nunca_resuelve():
    assert resolve_recipient("Lаura vecina", AGENDA).kind is not Kind.RESOLVED


def test_limite_maximo_tres_opciones():
    agenda = tuple(contact(f"laura-{i}", f"Laura {w}") for i, w in enumerate(["uno", "dos", "tres", "cuatro"]))
    assert len(resolve_recipient("Laura", agenda).options) == 3


@pytest.mark.parametrize("reply,offered,kind", [
    ("sí", (Option("carmen", "Carmen"),), Kind.RESOLVED),
    ("no", (Option("carmen", "Carmen"),), Kind.UNCLEAR),
    ("sí", OFFERED, Kind.UNCLEAR),
    ("Laura vecina", OFFERED, Kind.RESOLVED),
    ("laura-hija", (), Kind.UNCLEAR),
    ("pedro", (Option("pedro", "Pedro"),), Kind.UNCLEAR),
    (None, OFFERED, Kind.UNCLEAR),
])
def test_limite_eleccion(reply, offered, kind):
    agenda = TWO_LAURAS + (contact("carmen", "Carmen"),)
    assert resolve_choice(reply, offered, agenda).kind is kind


def test_limite_la_wallet_sale_de_la_agenda_no_de_la_opcion():
    r = resolve_choice("laura-hija", (Option("laura-hija", "Otra persona"),), TWO_LAURAS)
    assert r.contact.wallet_address == TWO_LAURAS[0].wallet_address


def test_previously_paid_se_lee_de_la_agenda():
    assert {c.alias: c.previously_paid for c in AGENDA}["mi-hija"] is True


@pytest.mark.parametrize("rows", [
    [{"alias": "a", "name": "A", "walletAddress": "https://x", "previouslyPaid": False, "pin": "1"}],
    [{"alias": "a", "name": "A", "walletAddress": "https://x"}],
    [{"alias": "a", "name": "A", "walletAddress": "https://x", "previouslyPaid": False}] * 2,
    [{"alias": "a", "name": "A", "walletAddress": "http://x", "previouslyPaid": False}],
    [{"alias": "a", "name": "A", "walletAddress": "https://x", "previouslyPaid": "no"}],
    [{"alias": "Mi Hija", "name": "A", "walletAddress": "https://x", "previouslyPaid": False}],
])
def test_agenda_mal_formada(tmp_path, rows):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"contacts": rows}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_agenda(path)
