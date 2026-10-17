"""speech-transcription: audio en español -> Transcript, todo en memoria y sin dependencias externas.

Fase 1 (solo librería estándar): validación de la cabecera WAV (RIFF) antes de decodificar, filtro local
de no-habla previo a los motores, Groq solo con consentimiento explícito y respaldo local ante fallo,
timeout o límite de uso (429). Sin habla no se llama a ningún motor. La llave del proveedor nunca pasa por
aquí; el texto y el audio no van a logs ni a disco: la función devuelve datos y el orquestador loggea solo
request_id, motor y duración. Los motores reales (Groq whisper-large-v3-turbo, faster-whisper base) y la
cabecera WebM/Opus son Fase 2; hoy Decoder, SpeechFilter, RemoteEngine y LocalEngine son interfaces que los
dobles de prueba satisfacen estructuralmente.
Fuente de verdad: openspec/changes/add-voice-understanding/specs/speech-transcription/spec.md y
docs/voz/contrato-voz.md §3 y §4.
"""
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from voice.config import AUDIO_MAX_DURATION_S, MAX_REMOTE_ATTEMPTS, TURN_BUDGET_S

_WAV_MIN_BYTES = 12  # b"RIFF" + tamaño + b"WAVE"
_FMT_MIN_BYTES = 16


class Engine(str, Enum):
    GROQ = "groq"
    LOCAL = "local"
    NONE = "none"


class TranscribeErrorCode(str, Enum):
    INVALID_AUDIO = "INVALID_AUDIO"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"


class TranscribeInputError(Exception):
    """Error de validación del audio; el orquestador lo mapea a 400 { error: { code, message } } (B-3)."""

    def __init__(self, code: TranscribeErrorCode, message: str):
        self.code = code
        super().__init__(message)


class ProviderRateLimitError(Exception):
    """HTTP 429 del proveedor externo; retry_after_s viene de su cabecera retry-after."""

    def __init__(self, retry_after_s: int):
        self.retry_after_s = retry_after_s
        super().__init__(f"provider rate limited, retry after {retry_after_s}s")


@dataclass(frozen=True)
class Transcript:
    text: str
    had_speech: bool
    engine: Engine
    transcript_confidence: "float | None" = None  # sin fuente calibrada en H2: siempre None

    def to_dict(self) -> dict:
        """Forma del contrato HTTP: camelCase (B-7)."""
        return {"text": self.text, "hadSpeech": self.had_speech, "engine": self.engine.value,
                "transcriptConfidence": self.transcript_confidence}


class Decoder:
    """Protocolo: bytes crudos -> PCM en memoria (float32 16 kHz mono), una sola vez por turno, sin disco."""

    def decode(self, audio: bytes): ...


class SpeechFilter:
    """Protocolo del filtro local de no-habla: corre antes que cualquier motor y no usa métricas del
    proveedor."""

    def has_speech(self, pcm) -> bool: ...


class RemoteEngine:
    """Protocolo del proveedor externo (Groq whisper-large-v3-turbo), en español; solo recibe el audio."""

    def transcribe(self, pcm) -> str: ...


class LocalEngine:
    """Protocolo del respaldo local (faster-whisper base), en español."""

    def transcribe(self, pcm) -> str: ...


@dataclass(frozen=True)
class Engines:
    """Interfaces inyectadas por el orquestador; sleep espera los retry-after (None: no se puede esperar)."""
    decoder: Decoder
    speech_filter: SpeechFilter
    remote: RemoteEngine
    local: LocalEngine
    sleep: "Callable[[int], None] | None" = None


def _require_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")


def _wav_header(audio: bytes) -> "tuple[int, int, int] | None":
    """(byte_rate, data_size, data_offset) si `audio` es un WAV legible por cabecera; None si no lo es."""
    if len(audio) < _WAV_MIN_BYTES or audio[0:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return None
    byte_rate = None
    data_size = None
    data_offset = None
    pos = _WAV_MIN_BYTES
    while pos + 8 <= len(audio):
        chunk_id = audio[pos:pos + 4]
        chunk_size = int.from_bytes(audio[pos + 4:pos + 8], "little")
        body = pos + 8
        if chunk_id == b"fmt " and chunk_size >= _FMT_MIN_BYTES:
            fmt = audio[body:body + _FMT_MIN_BYTES]
            if len(fmt) < _FMT_MIN_BYTES:
                return None
            byte_rate = int.from_bytes(fmt[8:12], "little")
        elif chunk_id == b"data" and data_size is None:
            data_size = chunk_size
            data_offset = body
        if byte_rate is not None and data_size is not None:
            return byte_rate, data_size, data_offset
        pos = body + chunk_size + (chunk_size % 2)
    return None


def _validate_audio(audio: bytes) -> None:
    """INVALID_AUDIO y AUDIO_TOO_LONG como resultados de validación, leídos antes de decodificar."""
    if not isinstance(audio, bytes) or len(audio) == 0:
        raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO, "audio must be non-empty bytes")
    header = _wav_header(audio)
    if header is None:
        raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO,
                                   "unsupported or unreadable audio format")
    byte_rate, data_size, data_offset = header
    if byte_rate <= 0:
        raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO, "unreadable wav header")
    if data_size > byte_rate * AUDIO_MAX_DURATION_S:
        raise TranscribeInputError(TranscribeErrorCode.AUDIO_TOO_LONG,
                                   f"audio longer than {AUDIO_MAX_DURATION_S} s")
    if data_offset + data_size > len(audio):
        raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO, "truncated audio")


def transcribe(audio: bytes, request_id: str, consent_external: bool, engines: Engines) -> Transcript:
    """Convierte el audio de un turno en Transcript. El audio se decodifica una sola vez y el mismo buffer
    va al filtro y al motor. Sin consentimiento externo nunca se llama al proveedor; con él, Groq primero
    y respaldo local ante timeout, error o 429 cuyo retry-after no cabe en el plazo del turno."""
    _require_request_id(request_id)
    _validate_audio(audio)
    pcm = engines.decoder.decode(audio)
    if not engines.speech_filter.has_speech(pcm):
        return Transcript(text="", had_speech=False, engine=Engine.NONE)
    if not consent_external:
        return Transcript(engines.local.transcribe(pcm), True, Engine.LOCAL)
    attempts = 0
    while attempts < MAX_REMOTE_ATTEMPTS:
        attempts += 1
        try:
            return Transcript(engines.remote.transcribe(pcm), True, Engine.GROQ)
        except ProviderRateLimitError as err:
            can_wait = engines.sleep is not None and err.retry_after_s <= TURN_BUDGET_S
            if attempts >= MAX_REMOTE_ATTEMPTS or not can_wait:
                break
            engines.sleep(err.retry_after_s)
        except Exception:
            break
    return Transcript(engines.local.transcribe(pcm), True, Engine.LOCAL)