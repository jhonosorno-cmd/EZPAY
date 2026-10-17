"""Verificación de hablante: ECAPA (SpeechBrain) en CPU, un candado, fallo cerrado.

`verify(pcm, user)` es EXACTAMENTE el `context.voice` que consume el motor de
decisión: `{"status": "VERIFIED"|"BELOW_THRESHOLD"|"NOT_AVAILABLE", "score"}`.
El modelo carga UNA vez en `load()` al arrancar; nunca en una petición. Todo
fallo (modelo caído, audio inválido, usuario sin huella) devuelve
NOT_AVAILABLE sin excepción (SEG-6). `score` es el coseno entre el embedding
del comando y la huella guardada; VERIFIED si `score >= umbral`.
"""
import logging
import os
import threading

import numpy as np

from speaker.audio import SAMPLE_RATE, duracion_voz_util, trim_silence
from speaker.store import SpeakerStore

logger = logging.getLogger(__name__)

UMBRAL_DEFECTO = 0.45          # calibrado el 15 oct (calibrar_umbral.py)
MIN_VERIFY_SECONDS_DEFECTO = 2.0  # voz útil mínima para verificar
MAX_SEGUNDOS = 30.0            # por encima: NOT_AVAILABLE sin pasar por el modelo


class EcapaEmbedder:
    """Embedder real: SpeechBrain ECAPA (spkrec-ecapa-voxceleb), CPU, sin red."""

    def __init__(self, dir_modelo=None):
        self.dir_modelo = dir_modelo or os.environ.get("EZPAY_SPEAKER_MODEL_DIR")
        self._modelo = None

    def load(self):
        if not self.dir_modelo:
            raise RuntimeError("EZPAY_SPEAKER_MODEL_DIR is not set")
        os.environ["HF_HUB_OFFLINE"] = "1"  # antes de importar speechbrain: carga solo local
        from speechbrain.inference.speaker import EncoderClassifier

        self._modelo = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=self.dir_modelo,
            run_opts={"device": "cpu"})

    def embed(self, pcm):
        import torch

        wav = torch.tensor(np.asarray(pcm, dtype="float32")).unsqueeze(0)
        with torch.no_grad():
            salida = self._modelo.encode_batch(wav)
        vector = salida.squeeze().cpu().numpy().astype("float32")
        return vector / np.linalg.norm(vector)


class SpeakerVerifier:
    def __init__(self, store=None, embedder=None, umbral=UMBRAL_DEFECTO,
                 min_verify_seconds=MIN_VERIFY_SECONDS_DEFECTO):
        self.store = store if store is not None else SpeakerStore()
        self.embedder = embedder
        self.umbral = float(umbral)
        self.min_verify_seconds = float(min_verify_seconds)
        self.candado = threading.Lock()  # una verificación a la vez (SEG-2)
        self.error_de_carga = False
        self._cargado = False

    def load(self):
        """Carga el modelo UNA vez al arrancar. Si falla, queda degradado: todo
        verify devuelve NOT_AVAILABLE y el motor sigue en modo PIN (SEG-6)."""
        try:
            if self.embedder is None:
                self.embedder = EcapaEmbedder()
            cargador = getattr(self.embedder, "load", None)
            if cargador is not None:
                cargador()
            self._cargado = True
            self.error_de_carga = False
        except Exception as e:
            self.error_de_carga = True
            logger.warning("Speaker model failed to load; all verifications will return "
                           "NOT_AVAILABLE (%s)", type(e).__name__)

    def _listo(self):
        return self.embedder is not None and self._cargado and not self.error_de_carga

    def embed(self, pcm):
        """Embedding L2-normalizado del audio (recortando silencios), o None.

        Devuelve None sin tocar el modelo si el audio está vacío o pasa de
        MAX_SEGUNDOS (defensa en profundidad), o si el modelo no está listo.
        """
        pcm = np.asarray(pcm, dtype="float32")
        if pcm.size == 0 or pcm.size / SAMPLE_RATE > MAX_SEGUNDOS:
            return None
        if not self._listo():
            return None
        try:
            with self.candado:
                vector = np.asarray(self.embedder.embed(trim_silence(pcm)), dtype="float32")
            return vector / np.linalg.norm(vector)
        except Exception as e:
            logger.warning("Speaker model failed during embedding; verification "
                           "unavailable (%s)", type(e).__name__)
            return None

    def verify(self, pcm, user):
        """context.voice del motor: {"status", "score"}. Nunca lanza excepción."""
        pcm = np.asarray(pcm, dtype="float32")
        if pcm.size == 0 or pcm.size / SAMPLE_RATE > MAX_SEGUNDOS:
            return {"status": "NOT_AVAILABLE", "score": None}  # no entra al modelo
        if not self._listo():
            return {"status": "NOT_AVAILABLE", "score": None}  # modelo caído/no cargado
        huella = self.store.load(usuario=user)
        if huella is None:
            return {"status": "NOT_AVAILABLE", "score": None}  # usuario no enrolado
        if duracion_voz_util(pcm) < self.min_verify_seconds:  # voz útil insuficiente
            return {"status": "NOT_AVAILABLE", "score": None}
        embedding = self.embed(pcm)
        if embedding is None:
            return {"status": "NOT_AVAILABLE", "score": None}  # fallo interno del modelo
        score = float(np.dot(embedding, np.asarray(huella, dtype="float32")))
        if score >= self.umbral:  # el borde (score == umbral) pasa
            return {"status": "VERIFIED", "score": score}
        return {"status": "BELOW_THRESHOLD", "score": score}