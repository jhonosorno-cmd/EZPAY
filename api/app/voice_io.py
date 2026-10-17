"""Adaptadores de audio: transcripción (Voz) y verificación/enrolamiento de hablante (ML 2).

Las dependencias pesadas (av, faster-whisper, speechbrain) se importan de forma perezosa: si no
están instaladas o el modelo no carga, el backend igual arranca. Sin transcripción, los turnos
de audio fallan con INTERNAL_ERROR (el texto sigue funcionando); sin modelo de hablante, toda
verificación es NOT_AVAILABLE y el motor pide PIN (SEG-6).

El audio se decodifica una sola vez por turno: el mismo PCM va al filtro de habla, al motor de
transcripción y a la verificación de hablante. Nada de esto va a disco ni a logs (PRIV-1, PRIV-4).
"""
import logging
import threading

from voice.transcribe import Engines, Transcript, transcribe

logger = logging.getLogger("ezpay.voice_io")

NOT_AVAILABLE = {"status": "NOT_AVAILABLE", "score": None}


class TranscriptionUnavailable(Exception):
    """Los motores de transcripción no están instalados en este entorno."""


class RemoteSttFailed(Exception):
    """Modo solo Groq: el proveedor falló y no hay respaldo local."""


class _LocalDisabled:
    """Respaldo local apagado (EZPAY_STT_PROVIDER=groq): si Groq falla, el turno falla."""

    def transcribe(self, pcm):
        raise RemoteSttFailed()


class _CapturingDecoder:
    """Envuelve el decoder de Voz para quedarse con el PCM y reusarlo en la verificación."""

    def __init__(self, inner):
        self._inner = inner
        self.pcm = None

    def decode(self, audio: bytes):
        self.pcm = self._inner.decode(audio)
        return self.pcm


class VoiceIO:
    def __init__(self, engines: Engines | None = None, verifier=None, enrollment=None, stt_provider: str = "groq"):
        self._engines = engines
        self.groq_only = stt_provider == "groq"
        self._engines_error = False
        self.verifier = verifier
        self.enrollment = enrollment

    # ---------------------------------------------------------------- arranque
    def load(self, warmup_local: bool = False) -> None:
        if self._engines is None:
            try:
                from voice.engines import build_default_engines
                engines = build_default_engines()
                if self.groq_only:
                    import os
                    engines = Engines(decoder=engines.decoder, speech_filter=engines.speech_filter,
                                      remote=engines.remote, local=_LocalDisabled(), sleep=engines.sleep)
                    if not os.environ.get("GROQ_API_KEY"):
                        logger.error("EZPAY_STT_PROVIDER=groq but GROQ_API_KEY is not set: audio turns will fail")
                self._engines = engines
            except Exception as exc:  # ImportError de av/faster-whisper/numpy
                self._engines_error = True
                logger.warning("Transcription engines unavailable (%s); audio turns will fail", type(exc).__name__)
        if self.verifier is None:
            try:
                from speaker import SpeakerEnrollment, SpeakerVerifier
                self.verifier = SpeakerVerifier()
                self.verifier.load()  # falla ⇒ degradado: todo verify da NOT_AVAILABLE
                self.enrollment = SpeakerEnrollment(self.verifier)
            except Exception as exc:  # numpy ausente
                logger.warning("Speaker verification unavailable (%s)", type(exc).__name__)
        if warmup_local and self._engines is not None and not self.groq_only:
            threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        """Carga faster-whisper en segundo plano para que el primer turno no espere la descarga."""
        try:
            import numpy as np
            self._engines.local.transcribe(np.zeros(1600, dtype="float32"))
            logger.info("Local whisper model ready")
        except Exception as exc:
            logger.warning("Local whisper warmup failed (%s)", type(exc).__name__)

    # ------------------------------------------------------------- enrolamiento
    @property
    def speaker_ready(self) -> bool:
        return self.verifier is not None and getattr(self.verifier, "_listo", lambda: False)()

    def enrolled(self) -> bool:
        if self.enrollment is None:
            return False
        return bool(self.enrollment.status()["enrolled"])

    def consent_external(self) -> bool:
        if self.groq_only:  # decisión del equipo (17 oct): la transcripción va siempre a Groq
            return True
        try:
            return bool(self.enrollment and self.enrollment.consent_external())
        except Exception:
            return False

    def decode(self, audio: bytes):
        """Bytes → PCM con el decoder de Voz; TranscribeInputError si no se puede leer."""
        if self._engines is None:
            raise TranscriptionUnavailable()
        return self._engines.decoder.decode(audio)

    # ------------------------------------------------------------------- turno
    def transcribe_command(self, audio: bytes, request_id: str, verify: bool) -> tuple[Transcript, dict]:
        """Transcribe el audio y, si `verify`, verifica la voz del mismo PCM (solo comandos, D4).

        Devuelve (Transcript, context.voice). Lanza TranscribeInputError (INVALID_AUDIO,
        AUDIO_TOO_LONG) o TranscriptionUnavailable.
        """
        if self._engines is None:
            raise TranscriptionUnavailable()
        capture = _CapturingDecoder(self._engines.decoder)
        engines = Engines(decoder=capture, speech_filter=self._engines.speech_filter,
                          remote=self._engines.remote, local=self._engines.local, sleep=self._engines.sleep)
        transcript = transcribe(audio, request_id, self.consent_external(), engines)
        voice = NOT_AVAILABLE
        if verify and transcript.had_speech and capture.pcm is not None and self.verifier is not None:
            try:
                voice = self.verifier.verify(capture.pcm, user="usuario")
            except Exception as exc:
                logger.warning("Speaker verification failed (%s)", type(exc).__name__)
                voice = NOT_AVAILABLE
        return transcript, voice
