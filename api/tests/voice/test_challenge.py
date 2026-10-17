"""confirmation-challenge: banco de frases, elección sin repetir, coincidencia (80 %) y textos del desafío."""
import json
import random

import pytest

from voice.amounts import Amount
from voice.challenge import (CHALLENGE_MIN_MATCH, FORBIDDEN_WORDS, challenge_matches, load_bank, phrase_match,
                             pick_phrase)
from voice.config import CHALLENGE_BANK_PATH
from voice.phrases import Situation, say
from voice.replies import Reply, classify_reply
from voice.text import words

# Frases del registro de voz (web/src/enrollment/content.ts): el desafío no las puede repetir.
ENROLLMENT = ["Hoy es un buen día para enviarle dinero a mi familia.", "Mi voz es mi firma y la uso para mis envíos.",
              "Quiero pagar hablando, de forma segura y sencilla."]
FRASE = "Mi casa tiene una puerta verde y grande."


# --- el banco
def test_el_banco_real_tiene_al_menos_30_frases():
    assert len(load_bank()) >= 30


def test_cada_frase_tiene_de_6_a_9_palabras():
    for frase in load_bank():
        assert 6 <= len(words(frase)) <= 9, frase


def test_sin_numeros_ni_palabras_prohibidas():
    for frase in load_bank():
        palabras = set(words(frase))
        assert not any(c.isdigit() for c in frase), frase
        assert not palabras & FORBIDDEN_WORDS, (frase, palabras & FORBIDDEN_WORDS)


def test_ninguna_frase_es_afirmacion_ni_negacion_ni_contiene_una_sola():
    for frase in load_bank():
        assert classify_reply(frase) is Reply.UNCLEAR, frase


def test_sin_repetidas_ni_iguales_a_las_del_registro_de_voz():
    bank = load_bank()
    claves = [" ".join(words(f)) for f in bank]
    assert len(set(claves)) == len(claves)
    assert not set(claves) & {" ".join(words(f)) for f in ENROLLMENT}


def test_banco_con_menos_de_30_o_frase_invalida_no_carga(tmp_path):
    corto = tmp_path / "b.json"
    corto.write_text(json.dumps({"phrases": [FRASE] * 5}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_bank(corto)
    malo = tmp_path / "m.json"
    malo.write_text(json.dumps({"phrases": [f"Frase número {i} de prueba larga hoy" for i in range(40)]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_bank(malo)  # tiene dígitos o palabras prohibidas


def test_ruta_del_banco_es_configurable():
    assert CHALLENGE_BANK_PATH.name == "challenge_phrases.json"


# --- elección sin repetir
def test_pick_no_repite_las_usadas():
    bank = load_bank()
    usadas = set(bank[:-1])
    assert pick_phrase(bank, usadas, random.Random(1)) == bank[-1]


def test_pick_con_todas_usadas_evita_solo_la_ultima():
    bank = load_bank()
    for semilla in range(30):
        assert pick_phrase(bank, set(bank), random.Random(semilla), last=bank[0]) != bank[0]


def test_pick_devuelve_frases_del_banco_y_es_reproducible():
    bank = load_bank()
    a = pick_phrase(bank, set(), random.Random(7))
    assert a in bank and a == pick_phrase(bank, set(), random.Random(7))


# --- coincidencia
def test_frase_identica_da_1():
    assert phrase_match(FRASE, FRASE) == 1.0


def test_ignora_mayusculas_tildes_y_signos():
    assert phrase_match("mi CASA tiene una puérta verde y grande!!", FRASE) == 1.0


def test_un_error_de_8_palabras_da_0875_y_cumple():
    t = "Mi casa tiene una puerta roja y grande."
    assert phrase_match(t, FRASE) == 0.875 and challenge_matches(t, FRASE)


def test_dos_errores_de_8_dan_075_y_no_cumple():
    t = "Mi casa tiene una puerta roja y pequeña."
    assert phrase_match(t, FRASE) == 0.75 and not challenge_matches(t, FRASE)


def test_una_palabra_de_relleno_al_inicio_se_tolera():
    t = " Y mi casa tiene una puerta verde y grande."   # Whisper suele añadir "Y"
    assert challenge_matches(t, FRASE)


def test_silencio_vacio_o_no_texto_da_0():
    for t in ("", "   ", None, 5):
        assert phrase_match(t, FRASE) == 0.0 and not challenge_matches(t, FRASE)


def test_orden_distinto_baja_el_puntaje():
    assert phrase_match("grande y verde puerta una tiene casa mi", FRASE) < CHALLENGE_MIN_MATCH


def test_el_corte_es_080():
    assert CHALLENGE_MIN_MATCH == 0.80


def test_frase_esperada_vacia_es_error():
    with pytest.raises(ValueError):
        phrase_match("hola", "")


def test_otra_frase_del_banco_no_cumple():
    bank = load_bank()
    assert not challenge_matches(bank[1], bank[0])


# --- textos
def test_confirm_challenge_dice_monto_destinatario_y_frase():
    texto = say(Situation.CONFIRM_CHALLENGE, amount=Amount("2000000", "COP", 2), name="Laura", phrase=FRASE)
    assert texto == ("¿Le envío 20.000 pesos a Laura? Para confirmar, repite: "
                     "Mi casa tiene una puerta verde y grande.")


def test_challenge_retry_pide_otra_vez_con_la_frase():
    texto = say(Situation.CHALLENGE_RETRY, phrase=FRASE)
    assert FRASE in texto and "repite" in texto.lower()


@pytest.mark.parametrize("situacion,params", [
    (Situation.CONFIRM_CHALLENGE, {"amount": Amount("2000000", "COP", 2), "name": "Laura"}),
    (Situation.CONFIRM_CHALLENGE, {"name": "Laura", "phrase": FRASE}),
    (Situation.CHALLENGE_RETRY, {}),
    (Situation.CHALLENGE_RETRY, {"phrase": FRASE, "name": "Laura"}),
])
def test_parametros_faltantes_o_de_mas_son_error(situacion, params):
    with pytest.raises(ValueError):
        say(situacion, **params)


@pytest.mark.parametrize("frase", ["", "   ", None, 5])
def test_frase_vacia_o_no_texto_en_say_es_error(frase):
    with pytest.raises(ValueError):
        say(Situation.CHALLENGE_RETRY, phrase=frase)


# --- Situaciones que pidió ML 2 (add-ml2-integration, tarea 1.3)
def test_confirm_challenge_overrun_avisa_del_exceso_y_pide_la_frase():
    texto = say(Situation.CONFIRM_CHALLENGE_OVERRUN, amount=Amount("2000000", "COP", 2), name="Laura", phrase=FRASE)
    assert texto == ("¿Le envío 20.000 pesos a Laura? Supera tu presupuesto y lo autorizarás en tu billetera. "
                     "Para confirmar, repite: Mi casa tiene una puerta verde y grande.")


def test_challenge_failed_rechaza_sin_enviar_nada():
    assert say(Situation.CHALLENGE_FAILED) == "No coincidió la frase. No envié nada."


@pytest.mark.parametrize("situacion,params", [
    (Situation.CONFIRM_CHALLENGE_OVERRUN, {"amount": Amount("2000000", "COP", 2), "name": "Laura"}),
    (Situation.CONFIRM_CHALLENGE_OVERRUN, {"name": "Laura", "phrase": FRASE}),
    (Situation.CHALLENGE_FAILED, {"phrase": FRASE}),
])
def test_parametros_de_las_situaciones_nuevas_son_estrictos(situacion, params):
    with pytest.raises(ValueError):
        say(situacion, **params)
