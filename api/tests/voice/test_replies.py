"""Pruebas de reply-classification: una por escenario de
openspec/changes/add-voice-understanding/specs/reply-classification/spec.md, más las frases de
docs/voz/frases-desarrollo.md (sección C) y casos límite. "Sin llamada al LLM": test_package.py."""
import pytest

from voice.replies import Reply, classify_reply

YES, NO, UNCLEAR = Reply.YES, Reply.NO, Reply.UNCLEAR


# --- Escenarios del spec
def test_afirmacion_clara():
    assert classify_reply("sí") is YES


def test_negacion_clara():
    assert classify_reply("no") is NO


def test_respuesta_dudosa():
    assert classify_reply("eh… ¿cuánto?") is UNCLEAR


def test_afirmacion_y_negacion():
    assert classify_reply("sí, no") is UNCLEAR


def test_respuesta_vacia():
    assert classify_reply("") is UNCLEAR


def test_cambio_de_monto_en_la_confirmacion():
    assert classify_reply("sí, mejor 50 mil") is UNCLEAR


def test_eco_de_la_pregunta_del_sistema():
    assert classify_reply("¿Le envío 20.000 a Laura?") is UNCLEAR


# --- Frases de desarrollo, sección C
@pytest.mark.parametrize("text,expected", [
    ("sí", YES), ("Sí, sí.", YES), ("dale", YES), ("claro que sí", YES), ("sí por favor", YES),
    ("no", NO), ("cancela", NO),
    ("claro", UNCLEAR), ("ok", UNCLEAR), ("eh… ¿cuánto?", UNCLEAR), ("sí, no", UNCLEAR),
    ("no, sí", UNCLEAR), ("sí, mejor 50 mil", UNCLEAR), ("¿Le envío 20.000 a Laura?", UNCLEAR),
    ("Gracias.", UNCLEAR), ("¡Suscríbete!", UNCLEAR), ("", UNCLEAR),
])
def test_frases_seccion_c(text, expected):
    assert classify_reply(text) is expected


# --- Casos límite
@pytest.mark.parametrize("text", [
    "¡SÍ!", "si", "Sí…", "sí sí sí", "sí gracias", "Sí, por favor, gracias", "sí claro que sí",
    "de acuerdo", "confirmo", "Dale, gracias",
])
def test_limite_si(text):
    assert classify_reply(text) is YES


@pytest.mark.parametrize("text", ["no no", "no gracias", "No, cancela", "nada", "detente", "para", "cancelar"])
def test_limite_no(text):
    assert classify_reply(text) is NO


@pytest.mark.parametrize("text", [
    "bueno", "listo", "vale", "va", "ajá", "mmm", "por favor", "sí señora", "estoy de acuerdo",
    "no sé", "sí, no sé", "sí 20", "1234", "si quieres", "sí a José", "sí, a Laura vecina",
])
def test_limite_unclear(text):
    assert classify_reply(text) is UNCLEAR


HOSTILE = [
    "s​í", "ѕі", "sí " * 101, "sí\x00", "sí; DROP TABLE", "SÍ" + "!" * 300,
    "yes", "ѕí", "s i", "no" + " no" * 120,
]


@pytest.mark.parametrize("text", HOSTILE, ids=[f"hostil{i}" for i in range(len(HOSTILE))])
def test_hostiles_nunca_son_si(text):
    assert classify_reply(text) is not YES


@pytest.mark.parametrize("bad", [None, 1, b"si", ["si"], 2.5])
def test_entrada_que_no_es_texto(bad):
    assert classify_reply(bad) is UNCLEAR
