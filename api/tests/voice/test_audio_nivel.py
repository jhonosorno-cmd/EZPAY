"""scripts/audio_nivel.py: nivel de una grabación (para ajustar la ganancia) y elección del micrófono."""
import numpy as np
import pytest

from scripts.audio_nivel import nivel, resolver_dispositivo

SR = 16000
RNG = np.random.default_rng(3)


def _con_habla(amplitud, ruido=0.002, segundos=3):
    x = RNG.normal(0.0, ruido, SR * segundos).astype("float32")
    t = np.arange(SR, dtype="float32") / SR
    x[SR:2 * SR] += (amplitud * np.sin(2 * np.pi * 220.0 * t)).astype("float32")
    return x


def test_habla_normal_es_ok():
    n = nivel(_con_habla(0.3))
    assert n.veredicto == "OK" and 0.1 < n.habla < 0.4


def test_habla_muy_baja_pide_subir_la_ganancia():
    n = nivel(_con_habla(0.01))
    assert n.veredicto == "MUY BAJO"


def test_audio_saturado_pide_bajar_la_ganancia():
    x = _con_habla(1.5)
    n = nivel(np.clip(x, -1.0, 1.0))
    assert n.pico >= 0.99 and n.veredicto == "SATURADO"


def test_ruido_parecido_a_la_voz_se_avisa():
    n = nivel(_con_habla(0.03, ruido=0.02))
    assert n.veredicto == "MUCHO RUIDO"


def test_silencio_o_vacio_no_rompe():
    assert nivel(np.zeros(SR, dtype="float32")).veredicto == "SIN VOZ"
    assert nivel(np.zeros(0, dtype="float32")).veredicto == "SIN VOZ"


def test_el_texto_resumen_trae_los_numeros():
    texto = nivel(_con_habla(0.3)).texto()
    assert "pico" in texto and "OK" in texto


DISPOSITIVOS = [
    {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2},
    {"name": "Micrófono (Conexant SmartAudio HD)", "max_input_channels": 2},
    {"name": "Altavoces", "max_input_channels": 0},
    {"name": "Auriculares con micrófono (Soundmates V2)", "max_input_channels": 1},
]


def test_sin_valor_usa_el_dispositivo_por_defecto():
    assert resolver_dispositivo("", DISPOSITIVOS) is None
    assert resolver_dispositivo(None, DISPOSITIVOS) is None


def test_por_numero():
    assert resolver_dispositivo("1", DISPOSITIVOS) == 1


def test_por_parte_del_nombre_sin_mayusculas_ni_tildes():
    assert resolver_dispositivo("soundmates", DISPOSITIVOS) == 3
    assert resolver_dispositivo("MICROFONO", DISPOSITIVOS) == 1


@pytest.mark.parametrize("valor", ["99", "-1", "2", "no existe", "Altavoces"])
def test_invalido_o_sin_entrada_es_error_claro(valor):
    with pytest.raises(ValueError):
        resolver_dispositivo(valor, DISPOSITIVOS)
