"""Fixtures de las pruebas de `speaker`: embedder FALSO determinista y audio sintético.

Sin modelo, sin red, sin torch: el embedder falso deriva el embedding de la
frecuencia dominante del audio (cruces por cero), de forma determinista.
"""
import threading
import time

import numpy as np

from speaker.audio import SAMPLE_RATE


def tono(f, segundos=4.0, silencio_inicial=0.5, silencio_final=0.5, amplitud=0.2):
    """Tono puro con silencio al inicio y al final, como una frase grabada."""
    n_i = int(silencio_inicial * SAMPLE_RATE)
    n_f = int(silencio_final * SAMPLE_RATE)
    n_voz = int(round((segundos - silencio_inicial - silencio_final) * SAMPLE_RATE))
    t = np.arange(n_voz) / SAMPLE_RATE
    voz = (amplitud * np.sin(2 * np.pi * f * t)).astype("float32")
    return np.concatenate([np.zeros(n_i, "float32"), voz, np.zeros(n_f, "float32")]).astype("float32")


def vector_en(angulo, dims=8):
    """Embedding L2-normalizado en el plano (cos θ, sin θ, 0...)."""
    v = np.zeros(dims, dtype="float32")
    v[0], v[1] = np.cos(angulo), np.sin(angulo)
    return v / np.linalg.norm(v)


def frecuencia_dominante(pcm):
    """Frecuencia estimada por cruces por cero; None si no hay señal."""
    pcm = np.asarray(pcm, dtype="float32")
    if pcm.size < 2 or float(np.abs(pcm).max()) == 0.0:
        return None
    cruces = np.count_nonzero(np.diff(np.signbit(pcm)))
    return cruces / 2.0 * SAMPLE_RATE / (pcm.size - 1)


class EmbedderFalso:
    """Embedder falso determinista: θ(f) = 2π·f/1000 sobre la esfera (8 dims).

    Cuenta cargas, llamadas y concurrencia máxima para las pruebas de carga,
    candado y privacidad. `fallo_al_cargar` simula un modelo que no carga y
    `fallo_al_embed` un error interno en cada embed.
    """

    def __init__(self, fallo_al_cargar=False, fallo_al_embed=False, latencia=0.0):
        self.cargas = 0
        self.llamadas = 0
        self.en_proceso = 0
        self.max_concurrencia = 0
        self.fallo_al_cargar = fallo_al_cargar
        self.fallo_al_embed = fallo_al_embed
        self.latencia = latencia
        self._candado = threading.Lock()

    def load(self):
        self.cargas += 1
        if self.fallo_al_cargar:
            raise RuntimeError("carga simulada fallida")

    def embed(self, pcm):
        with self._candado:
            self.llamadas += 1
            self.en_proceso += 1
            self.max_concurrencia = max(self.max_concurrencia, self.en_proceso)
        try:
            if self.latencia:
                time.sleep(self.latencia)
            if self.fallo_al_embed:
                raise RuntimeError("fallo simulado del modelo")
            f = frecuencia_dominante(pcm)
            angulo = (2 * np.pi * (f or 0.0) / 1000.0) % (2 * np.pi)
            return vector_en(angulo)
        finally:
            with self._candado:
                self.en_proceso -= 1


class EmbedderFijo(EmbedderFalso):
    """Devuelve SIEMPRE un vector fijo (para el escenario del borde: score == umbral)."""

    def __init__(self, embedding):
        super().__init__()
        self.vector = np.asarray(embedding, dtype="float32")

    def embed(self, pcm):
        with self._candado:
            self.llamadas += 1
            self.en_proceso += 1
            self.max_concurrencia = max(self.max_concurrencia, self.en_proceso)
        try:
            if self.latencia:
                time.sleep(self.latencia)
            return self.vector
        finally:
            with self._candado:
                self.en_proceso -= 1


F_DUEÑO = 150.0     # "hablante" genuino del huerto de pruebas
F_IMPOSTOR = 700.0  # "otra persona"