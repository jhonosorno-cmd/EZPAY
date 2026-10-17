"""Persistencia de la huella: embeddings y marca de consentimiento, NUNCA audio (PRIV-1).

Directorio configurable por `EZPAY_SPEAKER_DATA_DIR` (por defecto
`api/.data/speaker/`, fuera de git: crea un `.gitignore` con `*` dentro).
Escritura atómica: archivo temporal + rename. Usuario único (userId fijo del MVP).
"""
import json
import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ARCHIVO_HUELLA = "huella.npy"
ARCHIVO_CONSENTIMIENTO = "consent.json"


def directorio_por_defecto():
    """api/.data/speaker/ relativo a este paquete, o la variable de entorno."""
    entorno = os.environ.get("EZPAY_SPEAKER_DATA_DIR")
    if entorno:
        return Path(entorno)
    return Path(__file__).resolve().parent.parent / ".data" / "speaker"


class SpeakerStore:
    def __init__(self, ruta=None):
        self.directorio = Path(ruta) if ruta else directorio_por_defecto()

    def _preparar_directorio(self):
        self.directorio.mkdir(parents=True, exist_ok=True)
        gitignore = self.directorio / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n", encoding="utf-8")  # fuera de git, PRIV-1

    def _reemplazar_atomico(self, destino, datos_bytes):
        """Archivo temporal + rename: la huella nunca queda a medias (B-5)."""
        self._preparar_directorio()
        temporal = destino.with_suffix(destino.suffix + ".tmp")
        with open(temporal, "wb") as f:
            f.write(datos_bytes)
        os.replace(temporal, destino)

    def save(self, embedding, usuario, consent_externo=True):
        """Guarda el embedding L2-normalizado y la marca de consentimiento. Nunca audio."""
        vector = np.asarray(embedding, dtype="float32")
        self._reemplazar_atomico(self.directorio / ARCHIVO_HUELLA, vector.tobytes())
        marca = {"consentExterno": bool(consent_externo), "usuario": usuario}
        self._reemplazar_atomico(self.directorio / ARCHIVO_CONSENTIMIENTO,
                                 json.dumps(marca, ensure_ascii=False).encode("utf-8"))

    def load(self, usuario):
        """Embedding guardado para `usuario`, o None (no enrolado)."""
        ruta = self.directorio / ARCHIVO_HUELLA
        marca = self.directorio / ARCHIVO_CONSENTIMIENTO
        if not ruta.exists() or not marca.exists():
            return None
        datos = json.loads(marca.read_text(encoding="utf-8"))
        if datos.get("usuario") != usuario:
            return None
        return np.frombuffer(ruta.read_bytes(), dtype="float32")

    def huella_existe(self):
        return (self.directorio / ARCHIVO_HUELLA).exists()

    def consent_externo(self):
        marca = self.directorio / ARCHIVO_CONSENTIMIENTO
        if not marca.exists():
            return False
        datos = json.loads(marca.read_text(encoding="utf-8"))
        return bool(datos.get("consentExterno", False))

    def delete(self):
        """Borra huella y consentimiento (PRIV-3). Devuelve True si había huella."""
        habia = self.huella_existe()
        for nombre in (ARCHIVO_HUELLA, ARCHIVO_CONSENTIMIENTO):
            ruta = self.directorio / nombre
            if ruta.exists():
                ruta.unlink()
        return habia