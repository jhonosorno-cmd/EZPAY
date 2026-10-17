"""Persistencia del estado global del PIN: JSON con {"globalFailures", "locked"}.

"Junto a la huella" del hablante: directorio configurable por
`EZPAY_PIN_DATA_DIR`, por defecto `api/.data/pin/`, con un `.gitignore` con
`*` dentro (fuera de git, como `api/.data/speaker/`). Guarda SOLO el contador
global y el bloqueo: NUNCA el PIN, ni el hash, ni contadores de sesión (los de
sesión siguen en la memoria del proceso). Escritura atómica (archivo temporal
+ `os.replace`). Archivo ilegible o corrupto ⇒ falla cerrado: se trata como
`locked: true` con un aviso en el log sin datos sensibles;
`scripts/reset_pin_lock.py` lo repara (escribe {0, false}).
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ARCHIVO_ESTADO = "estado.json"
ESTADO_LIMPIO = {"globalFailures": 0, "locked": False}


def directorio_por_defecto():
    """api/.data/pin/ relativo a este paquete, o la variable de entorno."""
    entorno = os.environ.get("EZPAY_PIN_DATA_DIR")
    if entorno:
        return Path(entorno)
    return Path(__file__).resolve().parent.parent / ".data" / "pin"


class PinStore:
    def __init__(self, ruta=None):
        self.directorio = Path(ruta) if ruta else directorio_por_defecto()

    def _preparar_directorio(self):
        self.directorio.mkdir(parents=True, exist_ok=True)
        gitignore = self.directorio / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n", encoding="utf-8")  # fuera de git

    def _ruta_estado(self):
        return self.directorio / ARCHIVO_ESTADO

    def load(self):
        """(globalFailures, locked). Ausente ⇒ (0, False). Corrupto ⇒ (0, True)."""
        ruta = self._ruta_estado()
        if not ruta.exists():
            return 0, False
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            fallos, bloqueado = datos["globalFailures"], datos["locked"]
            if isinstance(fallos, bool) or not isinstance(fallos, int) or not isinstance(bloqueado, bool):
                raise ValueError("unexpected state types")
            return fallos, bloqueado
        except Exception as exc:
            logger.warning("PIN state file is corrupt or unreadable; treating as locked (%s)",
                           type(exc).__name__)
            return 0, True

    def save(self, global_failures, locked):
        """Escribe {globalFailures, locked} de forma atómica (temporal + rename)."""
        self._preparar_directorio()
        destino = self._ruta_estado()
        temporal = Path(str(destino) + ".tmp")
        with open(temporal, "wb") as f:
            f.write(json.dumps({"globalFailures": int(global_failures), "locked": bool(locked)},
                               ensure_ascii=False).encode("utf-8"))
        os.replace(temporal, destino)

    def reset(self):
        """Estado limpio {0, false}: repara también un archivo corrupto."""
        self.save(0, False)