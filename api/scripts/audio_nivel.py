"""Nivel de una grabación y elección del micrófono para los scripts de prueba a mano (solo desarrollo).

Sirve para saber si el problema es la ganancia del micrófono (muy bajo, saturado o con mucho ruido) antes de culpar a
la transcripción. No guarda ni envía audio.
"""
from dataclasses import dataclass

import numpy as np

from voice.text import fold

FRAME = 320  # 20 ms a 16 kHz


@dataclass(frozen=True)
class Nivel:
    pico: float
    habla: float      # nivel de los tramos más fuertes (percentil 95 del RMS por tramo de 20 ms)
    ruido: float      # nivel del fondo (percentil 20)
    veredicto: str    # OK | MUY BAJO | SATURADO | MUCHO RUIDO | SIN VOZ

    def texto(self) -> str:
        consejo = {
            "OK": "",
            "MUY BAJO": " -> sube la ganancia del micrófono en Windows o acércalo a la boca",
            "SATURADO": " -> baja la ganancia del micrófono o aléjalo",
            "MUCHO RUIDO": " -> el ruido de fondo es casi tan fuerte como tu voz; acerca el micrófono o baja el ruido",
            "SIN VOZ": " -> casi no se oyó nada: revisa que sea el micrófono correcto",
        }[self.veredicto]
        return f"pico {self.pico:.2f}, voz {self.habla:.3f}, fondo {self.ruido:.3f} -> {self.veredicto}{consejo}"


def nivel(pcm) -> Nivel:
    """Mide una grabación PCM float32 en [-1, 1] a 16 kHz."""
    x = np.asarray(pcm, dtype="float64").reshape(-1)
    n = x.size // FRAME
    if n == 0:
        return Nivel(0.0, 0.0, 0.0, "SIN VOZ")
    rms = np.sqrt(np.mean(np.square(x[: n * FRAME].reshape(n, FRAME)), axis=1))
    pico = float(np.max(np.abs(x)))
    habla, ruido = float(np.percentile(rms, 95)), float(np.percentile(rms, 20))
    if pico >= 0.99:
        veredicto = "SATURADO"
    elif habla < 0.004:
        veredicto = "SIN VOZ"
    elif habla < 0.02:
        veredicto = "MUY BAJO"
    elif habla < 3 * max(ruido, 1e-6):
        veredicto = "MUCHO RUIDO"
    else:
        veredicto = "OK"
    return Nivel(pico, habla, ruido, veredicto)


def resolver_dispositivo(valor, dispositivos) -> int | None:
    """Número o parte del nombre de un micrófono -> índice. Vacío = el dispositivo por defecto (None)."""
    if valor is None or not str(valor).strip():
        return None
    texto = str(valor).strip()
    con_entrada = [i for i, d in enumerate(dispositivos) if d["max_input_channels"] > 0]
    if texto.isdigit():
        if int(texto) in con_entrada:
            return int(texto)
        raise ValueError(f"el dispositivo {texto} no existe o no tiene entrada de audio")
    buscado = fold(texto)
    for i in con_entrada:
        if buscado in fold(dispositivos[i]["name"]):
            return i
    raise ValueError(f"no encontré un micrófono que contenga {texto!r}")
