"""scripts/desafio.py: evaluación y registro local del experimento del banco de frases del desafío."""
import csv
from pathlib import Path

import pytest

from scripts.desafio import CAMPOS, agregar_fila, evaluar, ruta_por_defecto, seleccionar

FRASE = "Mi casa tiene una puerta verde y grande."


def test_frase_dicha_bien_cumple():
    r = evaluar(FRASE, " Mi casa tiene una puerta verde y grande.", True)
    assert r.puntaje == 1.0 and r.veredicto == "CUMPLE"


def test_un_error_cumple_y_dos_no():
    assert evaluar(FRASE, "Mi casa tiene una puerta roja y grande", True).veredicto == "CUMPLE"
    r = evaluar(FRASE, "Mi casa tiene una puerta roja y pequeña", True)
    assert r.veredicto == "NO_CUMPLE" and r.puntaje == 0.75


def test_sin_voz_es_filtro_corto_con_puntaje_0():
    r = evaluar(FRASE, "", False)
    assert r.puntaje == 0.0 and r.veredicto == "FILTRO_CORTO"


def test_texto_vacio_con_voz_no_cumple():
    assert evaluar(FRASE, "", True).veredicto == "NO_CUMPLE"


def test_seleccion_vacia_es_todo_el_banco_con_su_numero():
    banco = ["a"] * 0 + [f"frase {i}" for i in range(1, 31)]
    assert [n for n, _ in seleccionar("", banco)] == list(range(1, 31))


def test_seleccion_por_numeros_y_rangos_y_errores():
    banco = [f"frase {i}" for i in range(1, 31)]
    assert [n for n, _ in seleccionar("1,3,5-7", banco)] == [1, 3, 5, 6, 7]
    for malo in ("0", "31", "x", "3-1"):
        with pytest.raises(ValueError):
            seleccionar(malo, banco)


def test_ruta_por_defecto_esta_fuera_del_repo():
    assert Path(__file__).resolve().parents[3] not in ruta_por_defecto().parents
    assert ruta_por_defecto().name == "desafio.csv"


def test_agregar_fila_crea_cabecera_una_vez_y_no_guarda_audio(tmp_path):
    ruta = tmp_path / "x" / "d.csv"
    r = evaluar(FRASE, "Mi casa tiene una puerta roja y grande", True)
    for n in (1, 2):
        agregar_fila(ruta, quien="sebas", ruido="silencio", numero=n, frase=FRASE, texto="Mi casa tiene una puerta roja y grande",
                     motor="groq", hubo_voz=True, resultado=r)
    filas = list(csv.DictReader(ruta.open(encoding="utf-8-sig")))
    assert len(filas) == 2 and list(filas[0]) == CAMPOS and filas[0]["puntaje"] == "0.875"
    assert filas[0]["veredicto"] == "CUMPLE" and "audio" not in CAMPOS
