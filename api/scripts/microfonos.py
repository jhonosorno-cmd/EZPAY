r"""Lista los micrófonos disponibles y prueba su nivel (solo desarrollo, Windows).

Uso (desde `api/`, en CMD):
  set PYTHONPATH=.
  .venv\Scripts\python.exe scripts\microfonos.py            # lista los micrófonos con su número
  .venv\Scripts\python.exe scripts\microfonos.py 5          # graba 3 s de ese micrófono y dice si el nivel es bueno

Para usar uno en las pruebas por voz:  set EZPAY_MICROFONO=5  (o una parte del nombre, por ejemplo: set EZPAY_MICROFONO=conexant)
"""
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audio_nivel import nivel, resolver_dispositivo  # noqa: E402

SEGUNDOS = 3


def _legible(nombre: str) -> str:
    """Los micrófonos Bluetooth traen una ruta larga de Windows; lo útil es el nombre entre paréntesis del final."""
    nombre = " ".join(nombre.split())
    if "@System32" in nombre and "(" in nombre:
        return f"{nombre.split(' ')[0]} {nombre.split(' ')[1]} ... {nombre[nombre.rindex('('):]}"
    return nombre


def main() -> int:
    dispositivos = sd.query_devices()
    apis = sd.query_hostapis()
    if len(sys.argv) < 2:
        por_defecto = sd.default.device[0]
        print("Micrófonos (el * es el que usan las pruebas si no eliges otro):")
        for i, d in enumerate(dispositivos):
            if d["max_input_channels"] > 0:
                marca = "*" if i == por_defecto else " "
                nombre = _legible(d["name"])[:70]
                print(f" {marca} {i:>3}  {nombre}  [{apis[d['hostapi']]['name']}, {int(d['default_samplerate'])} Hz]")
        return 0
    try:
        indice = resolver_dispositivo(sys.argv[1], dispositivos)
    except ValueError as err:
        print(err)
        return 1
    d = dispositivos[indice]
    rate = int(d["default_samplerate"])
    print(f"Probando: {' '.join(d['name'].split())}. Habla normal durante {SEGUNDOS} s...", flush=True)
    grabado = sd.rec(int(rate * SEGUNDOS), samplerate=rate, channels=1, dtype="float32", device=indice)
    sd.wait()
    x = grabado[:, 0]
    paso = max(1, rate // 16000)
    print("Nivel:", nivel(np.asarray(x[::paso], dtype="float32")).texto())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
