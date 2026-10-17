"""scripts/revision.py: después de grabar, escuchar (E), grabar de nuevo (R) o usar (ESPACIO), todo en memoria."""
import numpy as np

from scripts.revision import revisar


def _pcm(valor):
    return np.full(1600, valor, dtype="float32")


def _armar(teclas, grabaciones):
    registro = {"grabadas": 0, "reproducidas": [], "avisos": []}
    entrada = iter(teclas)
    graba = iter(grabaciones)

    def grabar():
        registro["grabadas"] += 1
        return next(graba)

    resultado = revisar(grabar, lambda: next(entrada), registro["reproducidas"].append, registro["avisos"].append)
    return resultado, registro


def test_espacio_usa_la_grabacion_sin_repetir():
    a = _pcm(0.1)
    r, reg = _armar([" "], [a])
    assert r is a and reg["grabadas"] == 1 and reg["reproducidas"] == []


def test_enter_tambien_usa_la_grabacion():
    a = _pcm(0.1)
    r, reg = _armar(["\r"], [a])
    assert r is a


def test_e_escucha_la_grabacion_y_sigue_esperando():
    a = _pcm(0.1)
    r, reg = _armar(["e", "E", " "], [a])
    assert r is a and reg["reproducidas"] == [a, a] and reg["grabadas"] == 1


def test_r_graba_de_nuevo_y_devuelve_la_ultima():
    a, b = _pcm(0.1), _pcm(0.2)
    r, reg = _armar(["r", " "], [a, b])
    assert r is b and reg["grabadas"] == 2


def test_escuchar_reproduce_la_grabacion_vigente_no_la_anterior():
    a, b = _pcm(0.1), _pcm(0.2)
    r, reg = _armar(["r", "e", " "], [a, b])
    assert reg["reproducidas"] == [b] and r is b


def test_otras_teclas_se_ignoran_y_se_avisa_el_menu_al_inicio():
    a = _pcm(0.1)
    r, reg = _armar(["x", "7", " "], [a])
    assert r is a and any("ESPACIO" in m and "E" in m and "R" in m for m in reg["avisos"])


def test_una_grabacion_vacia_no_se_puede_escuchar_y_se_avisa():
    vacio = np.zeros(0, dtype="float32")
    r, reg = _armar(["e", " "], [vacio])
    assert reg["reproducidas"] == [] and any("nada" in m.lower() for m in reg["avisos"])
