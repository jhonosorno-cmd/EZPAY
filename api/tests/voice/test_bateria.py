"""Pruebas del registro local de la batería de H3 (scripts/bateria.py): sin audio, fuera del repo."""
import csv
from pathlib import Path

import pytest

from scripts.bateria import (CAMPOS, FRASES, agregar_fila, evaluar, ruta_por_defecto, seleccionar_frases)


def esperado(decir):
    return next(f for f in FRASES if f.decir.startswith(decir))


# --- evaluar: qué hizo el sistema con el texto transcrito
def test_pago_correcto_es_ok():
    r = evaluar(esperado("Envíale veinte mil"), " Envíale 20.000 a Laura Hija", True)
    assert r.veredicto == "OK" and "PAY" in r.interpretado


def test_pago_con_monto_distinto_es_grave():
    r = evaluar(esperado("Envíale veinte mil"), "Envíale 200.000 a Laura hija", True)
    assert r.veredicto == "GRAVE"


def test_pago_con_nombre_mal_oido_es_nombre_mal():
    r = evaluar(esperado("Envíale veinte mil"), "Envíale 20.000 a la obra de IBA", True)
    assert r.veredicto == "NOMBRE_MAL"


def test_texto_que_no_se_entiende_es_seguro():
    r = evaluar(esperado("Envíale veinte mil"), " Yale 20.000 a Laura, hija.", True)
    assert r.veredicto == "SEGURO" and "UNKNOWN" in r.interpretado


def test_afirmativo_y_negativo_correctos_son_ok():
    assert evaluar(esperado("Sí"), " Sí", True).veredicto == "OK"
    assert evaluar(esperado("Cancela"), " Cancela", True).veredicto == "OK"


def test_respuesta_opuesta_a_la_esperada_es_grave():
    assert evaluar(esperado("Sí"), " No.", True).veredicto == "GRAVE"
    assert evaluar(esperado("No"), " Sí", True).veredicto == "GRAVE"


def test_respuesta_no_clara_cuando_se_esperaba_clara_es_seguro():
    assert evaluar(esperado("Confirmo"), " Confirma.", True).veredicto == "SEGURO"


def test_frase_poco_clara_se_espera_unclear():
    assert evaluar(esperado("Mmm"), " Mmm, no sé.", True).veredicto == "OK"


def test_silencio_sin_voz_es_ok_y_con_voz_es_seguro_si_no_dice_nada_util():
    assert evaluar(esperado("(silencio"), "", False).veredicto == "OK"
    assert evaluar(esperado("(silencio"), " Gracias.", True).veredicto == "FALSA_VOZ"


def test_habla_real_que_el_filtro_corto_es_perdida():
    assert evaluar(esperado("Envíale veinte mil"), "", False).veredicto == "FILTRO_CORTO"


# --- CSV local
def test_ruta_por_defecto_esta_fuera_del_repo():
    repo = Path(__file__).resolve().parents[3]
    assert repo not in ruta_por_defecto().parents


def test_agregar_fila_crea_el_archivo_con_cabecera_una_sola_vez(tmp_path):
    ruta = tmp_path / "sub" / "r.csv"
    frase = esperado("Sí")
    r = evaluar(frase, " Sí", True)
    agregar_fila(ruta, quien="ana", ruido="sala", numero=4, frase=frase, texto=" Sí", motor="groq",
                 hubo_voz=True, resultado=r)
    agregar_fila(ruta, quien="ana", ruido="sala", numero=5, frase=esperado("No"), texto="No.", motor="groq",
                 hubo_voz=True, resultado=evaluar(esperado("No"), "No.", True))
    filas = list(csv.DictReader(ruta.open(encoding="utf-8-sig")))
    assert [f["frase"] for f in filas] == ["Sí", "No"] and list(filas[0].keys()) == CAMPOS
    assert filas[0]["ruido"] == "sala" and filas[0]["quien"] == "ana" and filas[0]["veredicto"] == "OK"


def test_el_csv_no_guarda_audio_ni_llaves(tmp_path):
    ruta = tmp_path / "r.csv"
    frase = esperado("Sí")
    agregar_fila(ruta, quien="ana", ruido="", numero=1, frase=frase, texto="Sí", motor="local", hubo_voz=True,
                 resultado=evaluar(frase, "Sí", True))
    assert "audio" not in CAMPOS and not any("key" in c.lower() for c in CAMPOS)
    assert ruta.read_text(encoding="utf-8").count("gsk_") == 0


def test_hay_frases_de_todos_los_tipos_y_sin_duplicados():
    assert {f.tipo for f in FRASES} >= {"pago", "afirmativo", "negativo", "poco_clara", "silencio"}
    assert len({f.decir for f in FRASES}) == len(FRASES)


# --- --frases: elegir cuáles frases pedir
def test_sin_seleccion_pide_todas_con_su_numero_original():
    elegidas = seleccionar_frases("")
    assert [n for n, _ in elegidas] == list(range(1, len(FRASES) + 1))


def test_seleccion_por_comas_conserva_el_numero_y_el_orden_dado():
    elegidas = seleccionar_frases("1,3,9,10")
    assert [n for n, _ in elegidas] == [1, 3, 9, 10]
    assert elegidas[0][1] is FRASES[0] and elegidas[3][1] is FRASES[9]


def test_seleccion_acepta_rangos_y_espacios_y_no_repite():
    assert [n for n, _ in seleccionar_frases(" 1-3, 2 ,5")] == [1, 2, 3, 5]


@pytest.mark.parametrize("texto", ["0", "11", "99", "a", "1,,2x", "3-1", "-2"])
def test_seleccion_invalida_es_error_claro(texto):
    with pytest.raises(ValueError):
        seleccionar_frases(texto)
