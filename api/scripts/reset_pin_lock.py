"""Reinicio del bloqueo del PIN sobre el estado PERSISTIDO (H2, tarea 1.4).

Escribe {"globalFailures": 0, "locked": false} en el estado persistido
(EZPAY_PIN_DATA_DIR o api/.data/pin/) y también REPARA un archivo corrupto o
ilegible (que deja el validador bloqueado por falla cerrado).

El backend que está corriendo mantiene su estado en memoria: para levantarle
el bloqueo, reiniciarlo después de correr este script (o llamar a
`reset_pin_lock()` dentro del proceso, por ejemplo desde una ruta de
administración del orquestador, que también persiste).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pin.store import PinStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the persisted PIN lock state.")
    parser.add_argument("--data-dir", default=None,
                        help="Data directory (default: EZPAY_PIN_DATA_DIR or api/.data/pin/)")
    args = parser.parse_args()
    PinStore(args.data_dir).reset()
    print("Estado del PIN reiniciado: globalFailures=0, locked=false (persistido).")
    print("Si el backend está corriendo, reinicialo para que recargue el estado.")


if __name__ == "__main__":
    main()