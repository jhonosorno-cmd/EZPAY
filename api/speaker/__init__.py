"""Paquete `speaker`: verificación de hablante y enrolamiento de voz (ML 2).

API pública:
- SpeakerVerifier.load() / verify(pcm, user) -> context.voice del motor
- SpeakerEnrollment(verifier).enroll(samples, consent) / status() / delete()
- speaker.audio.trim_silence: recorte fijado por calibración (NO cambiar sin recalibrar)
- speaker.store.SpeakerStore: embeddings + consentimiento, nunca audio (PRIV-1)
"""
from speaker.audio import SAMPLE_RATE, duracion_voz_util, trim_silence
from speaker.enrollment import (CORTE_CONSISTENCIA_DEFECTO, EnrollmentError,
                                MAX_SEGUNDOS_MUESTRA, MIN_SEGUNDOS_MUESTRA,
                                SpeakerEnrollment)
from speaker.store import SpeakerStore
from speaker.verification import (EcapaEmbedder, MAX_SEGUNDOS,
                                  MIN_VERIFY_SECONDS_DEFECTO, SpeakerVerifier,
                                  UMBRAL_DEFECTO)

__all__ = [
    "SAMPLE_RATE", "trim_silence", "duracion_voz_util", "SpeakerStore", "SpeakerVerifier",
    "EcapaEmbedder", "SpeakerEnrollment", "EnrollmentError",
    "UMBRAL_DEFECTO", "MIN_VERIFY_SECONDS_DEFECTO", "MAX_SEGUNDOS",
    "MIN_SEGUNDOS_MUESTRA", "MAX_SEGUNDOS_MUESTRA", "CORTE_CONSISTENCIA_DEFECTO",
]