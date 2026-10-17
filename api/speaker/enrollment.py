"""Enrolamiento de voz (route B-2..B-5): 3 muestras, consentimiento, huella promedio.

Errores en orden fijo y mensajes que son SOLO el código (nada biométrico):
CONSENT_REQUIRED → SAMPLES_REQUIRED → INVALID_AUDIO → INCONSISTENT_SAMPLES.
La duración de cada muestra se mide DESPUÉS del recorte de silencios. La huella
es el promedio de los 3 embeddings, L2-normalizado. Un intento fallido no
cambia la huella anterior (escritura solo al final, atómica).
"""
import logging

import numpy as np

from speaker.audio import SAMPLE_RATE, duracion_voz_util, trim_silence

logger = logging.getLogger(__name__)

NUM_MUESTRAS = 3               # B-2: exactamente 3 muestras
MIN_SEGUNDOS_MUESTRA = 3.0     # B-3: por muestra, con la medida de la calibración (margen incluido)
MAX_SEGUNDOS_MUESTRA = 15.0
CORTE_CONSISTENCIA_DEFECTO = 0.45  # B-4: par mínimo por debajo ⇒ INCONSISTENT_SAMPLES
USUARIO_DEFECTO = "usuario"    # MVP de un solo usuario


class EnrollmentError(Exception):
    """Error del enrolamiento; el mensaje es solo el código, sin datos biométricos."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class SpeakerEnrollment:
    def __init__(self, verifier, corte_consistencia=CORTE_CONSISTENCIA_DEFECTO):
        self.verifier = verifier
        self.corte_consistencia = float(corte_consistencia)

    def status(self):
        """Consulta de estado: exactamente {"enrolled": bool}, nada más (B-6)."""
        return {"enrolled": self.verifier.store.huella_existe()}

    def consent_external(self):
        """consentExterno consultado por Voz: true si ya se enroló (contrato-voz §5)."""
        return self.verifier.store.consent_externo()

    def delete(self):
        """Borra huella y consentimiento (PRIV-3). Devuelve True si había huella."""
        return self.verifier.store.delete()

    def _rechazar(self, code):
        logger.info("Speaker enrollment rejected (%s)", code)  # solo el código: sin datos (PRIV-4)
        raise EnrollmentError(code)

    def enroll(self, samples, consent, usuario=USUARIO_DEFECTO):
        """Guarda la huella desde 3 muestras consistentes. Devuelve {"enrolled": True}."""
        if consent is not True:
            self._rechazar("CONSENT_REQUIRED")  # PRIMERO: sin consent no se procesa nada (PRIV-2)
        if len(samples) != NUM_MUESTRAS:
            self._rechazar("SAMPLES_REQUIRED")  # exactamente 3 (B-2)
        validas = []
        for muestra in samples:
            pcm = np.asarray(muestra, dtype="float32")
            recorte = trim_silence(pcm)
            if pcm.size == 0 or float(np.abs(pcm).max()) == 0.0 or recorte.size == 0:
                self._rechazar("INVALID_AUDIO")  # vacía o ilegible (B-3)
            duracion = duracion_voz_util(pcm)           # medida de la calibración, con margen (B-3)
            if duracion < MIN_SEGUNDOS_MUESTRA or duracion > MAX_SEGUNDOS_MUESTRA:
                self._rechazar("INVALID_AUDIO")
            validas.append(pcm)
        embeddings = []
        for pcm in validas:
            embedding = self.verifier.embed(pcm)
            if embedding is None:
                self._rechazar("INVALID_AUDIO")  # sin embedding usable
            embeddings.append(embedding)
        pares = [float(np.dot(embeddings[i], embeddings[j]))
                 for i in range(NUM_MUESTRAS) for j in range(i + 1, NUM_MUESTRAS)]
        if min(pares) < self.corte_consistencia:
            self._rechazar("INCONSISTENT_SAMPLES")  # parecen dos personas (B-4)
        promedio = np.mean(np.stack(embeddings), axis=0).astype("float32")
        norma = float(np.linalg.norm(promedio))
        if norma == 0.0:
            self._rechazar("INVALID_AUDIO")
        self.verifier.store.save(promedio / norma, usuario=usuario, consent_externo=True)
        logger.info("Speaker enrollment completed")  # sin datos biométricos (PRIV-4)
        return {"enrolled": True}