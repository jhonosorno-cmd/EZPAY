"""Script de reinicio del bloqueo del PIN (spec pin-validation).

Levanta el bloqueo y pone el contador global de fallos en 0.

H1: el contador global vive en la memoria del proceso del backend, así que
correr este script como proceso aparte NO afecta al backend en marcha. El
reinicio real en H1 es: reiniciar el backend, o llamar a `reset_pin_lock()`
dentro del proceso (por ejemplo desde una ruta de administración del
orquestador). Persistir el contador y el bloqueo se difiere a H2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pin.pin import default_validator, reset_pin_lock


def main() -> None:
    reset_pin_lock()
    print("Bloqueo del PIN levantado y contador global de fallos en 0 (instancia local).")
    print("H1: el contador del backend vive en la memoria de su proceso; reinicia el")
    print("backend o llama a reset_pin_lock() dentro del proceso para el reset real.")


if __name__ == "__main__":
    main()