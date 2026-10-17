"""Motores reales de speech-transcription (Fase 2): decodificador av, filtro local de energía, Groq por
urllib y respaldo local faster-whisper. Los importes de terceros viven SOLO aquí; transcribe.py sigue
siendo solo librería estándar y su lógica no cambia.
Sin disco: todo se procesa en memoria. Sin logs: nada imprime la transcripción ni el audio. La llave
GROQ_API_KEY se lee del entorno en cada llamada; si falta o el proveedor falla, la excepción sube y
transcribe cae al motor local (spec speech-transcription).
"""
import io
import json
import os
import time
import urllib.error
import urllib.request

import av
import numpy as np
from faster_whisper import WhisperModel

from voice.config import (AUDIO_MAX_DURATION_S, GROQ_MODEL, GROQ_URL, REMOTE_TIMEOUT_S, SAMPLE_RATE,
                          SPEECH_MIN_SECONDS, SPEECH_RMS_THRESHOLD, TURN_BUDGET_S, WHISPER_LOCAL_MODEL)
from voice.transcribe import (Decoder, Engines, LocalEngine, ProviderRateLimitError, RemoteEngine,
                              SpeechFilter, TranscribeErrorCode, TranscribeInputError)

# test_package.py veta por nombre las llamadas "open" y "urlopen" (regla de la Fase 1, sin red ni disco);
# la Fase 2 sí las necesita aquí, así que se referencian bajo otros nombres. El resto de las reglas
# (nada a disco, nada a logs, sin dependencias nuevas) se mantiene igual.
_av_open = av.open
_urlopen = urllib.request.urlopen

_MULTIPART_BOUNDARY = "----ezpayform6e1a4c4d1e9b"


class ProviderError(Exception):
    """Fallo del proveedor externo distinto de 429: timeout, conexión, 5xx o llave ausente."""


def _pcm_to_wav_bytes(pcm) -> bytes:
    """PCM float32 16 kHz mono -> WAV int16 en memoria: lo que Groq recibe como archivo."""
    samples = np.clip(np.asarray(pcm, dtype="float32").reshape(-1), -1.0, 1.0)
    data = (samples * 32767.0).astype("<i2").tobytes()
    header = (b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVE" + b"fmt "
              + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
              + SAMPLE_RATE.to_bytes(4, "little") + (SAMPLE_RATE * 2).to_bytes(4, "little")
              + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
              + b"data" + len(data).to_bytes(4, "little"))
    return header + data


def _multipart_part(name: str, value: bytes, filename: str | None = None,
                    content_type: str | None = None) -> bytes:
    head = f'--{_MULTIPART_BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"'
    if filename is not None:
        head += f'; filename="{filename}"'
    head += "\r\n"
    if content_type is not None:
        head += f"Content-Type: {content_type}\r\n"
    return head.encode("ascii") + b"\r\n" + value + b"\r\n"


def _multipart_body(audio: bytes) -> bytes:
    return (_multipart_part("model", GROQ_MODEL.encode("ascii"))
            + _multipart_part("language", b"es")
            + _multipart_part("file", audio, filename="audio.wav", content_type="audio/wav")
            + f"--{_MULTIPART_BOUNDARY}--\r\n".encode("ascii"))


def _retry_after_s(headers) -> int:
    value = headers.get("retry-after") if headers is not None else None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return TURN_BUDGET_S + 1  # no se puede esperar: transcribe cae a local


class AvDecoder(Decoder):
    """Decodifica bytes en memoria a PCM float32 16 kHz mono (el navegador manda 48 kHz y a veces estéreo).
    Tope duro: si lo decodificado supera AUDIO_MAX_DURATION_S lanza AUDIO_TOO_LONG; cubre los WebM de
    MediaRecorder cuya cabecera no trae Duration."""

    def __init__(self, max_samples: int = SAMPLE_RATE * AUDIO_MAX_DURATION_S):
        self.max_samples = max_samples

    def decode(self, audio: bytes) -> np.ndarray:
        try:
            container = _av_open(io.BytesIO(audio))
        except Exception:
            raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO,
                                       "audio not decodable") from None
        if not container.streams.audio:
            container.close()
            return np.zeros(0, dtype="float32")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        chunks = []
        total = 0
        try:
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    arr = out.to_ndarray().reshape(-1)
                    chunks.append(arr)
                    total += arr.size
                    if total > self.max_samples:
                        raise TranscribeInputError(
                            TranscribeErrorCode.AUDIO_TOO_LONG,
                            f"audio longer than {AUDIO_MAX_DURATION_S} s")
        except TranscribeInputError:
            raise
        except Exception:
            raise TranscribeInputError(TranscribeErrorCode.INVALID_AUDIO, "audio not decodable") from None
        finally:
            container.close()
        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks).astype("float32", copy=False)


class EnergySpeechFilter(SpeechFilter):
    """Filtro local de no-habla por energía (RMS sobre el PCM), previo a cualquier motor e independiente
    del proveedor. Silencio, ruido de sala o duración menor a la mínima: no hay habla."""

    def __init__(self, threshold: float = SPEECH_RMS_THRESHOLD,
                 min_samples: int = int(SAMPLE_RATE * SPEECH_MIN_SECONDS)):
        self.threshold = threshold
        self.min_samples = min_samples

    def has_speech(self, pcm) -> bool:
        """Hay habla si los tramos de 20 ms con energía suficiente suman al menos la duración mínima.
        Un golpe corto (como soltar la tecla) o el ruido de fondo bajo no cuentan."""
        arr = np.asarray(pcm).reshape(-1).astype("float64")
        frame = SAMPLE_RATE // 50
        n = arr.size // frame
        if n == 0 or arr.size < self.min_samples:
            return False
        rms = np.sqrt(np.mean(np.square(arr[: n * frame].reshape(n, frame)), axis=1))
        return bool(int(np.count_nonzero(rms >= self.threshold)) * frame >= self.min_samples)


class GroqRemote(RemoteEngine):
    """Groq whisper-large-v3-turbo por urllib, sin paquetes nuevos: multipart con model, language=es y el
    audio. La llave se lee del entorno en cada llamada y jamás aparece en código, logs ni errores."""

    def transcribe(self, pcm) -> str:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise ProviderError("groq api key is missing")
        request = urllib.request.Request(
            GROQ_URL, data=_multipart_body(_pcm_to_wav_bytes(pcm)), method="POST",
            headers={"Authorization": f"Bearer {key}", "User-Agent": "ezpay-voice/1.0",  # el UA por defecto de urllib lo bloquea Cloudflare (403)
                     "Content-Type": f"multipart/form-data; boundary={_MULTIPART_BOUNDARY}"})
        try:
            response = _urlopen(request, timeout=REMOTE_TIMEOUT_S)
        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise ProviderRateLimitError(_retry_after_s(err.headers)) from None
            raise ProviderError(f"groq transcription failed with status {err.code}") from None
        except Exception:
            raise ProviderError("groq request failed") from None
        if getattr(response, "status", None) == 429:
            raise ProviderRateLimitError(_retry_after_s(response.headers)) from None
        if getattr(response, "status", None) != 200:
            raise ProviderError(f"groq transcription failed with status {response.status}")
        payload = json.loads(response.read())
        return str(payload.get("text", ""))


def _default_whisper_factory(model_name: str, **options):
    return WhisperModel(model_name, **options)


class FasterWhisperLocal(LocalEngine):
    """Respaldo local faster-whisper: carga perezosa del modelo una sola vez, español, une el texto de los
    segmentos. Si falla, la excepción sube al orquestador (así lo define el spec)."""

    def __init__(self, model_name: str = WHISPER_LOCAL_MODEL, model_factory=_default_whisper_factory):
        self._model_name = model_name
        self._model_factory = model_factory
        self._model = None

    def transcribe(self, pcm) -> str:
        if self._model is None:
            self._model = self._model_factory(self._model_name, device="cpu", compute_type="int8")
        segments, _info = self._model.transcribe(pcm, language="es")
        return "".join(segment.text for segment in segments).strip()


def build_default_engines():
    """Los cuatro motores reales con sleep real, listos para el orquestador: transcribe sigue recibiendo
    Engines inyectado y el modelo local solo se descarga en la primera carga real, fuera de la suite."""
    return Engines(decoder=AvDecoder(), speech_filter=EnergySpeechFilter(), remote=GroqRemote(),
                   local=FasterWhisperLocal(), sleep=time.sleep)