"""Pruebas de los motores reales de Fase 2 (engines.py): decodificador av, filtro local de energía,
Groq por urllib y respaldo local faster-whisper. Nada toca la red ni el disco: el WebM se codifica en
memoria con av, Groq se prueba con monkeypatch de urlopen y el modelo local con un doble inyectado
(nunca se instancia WhisperModel ni se descarga el modelo). La llave en pruebas es siempre "test-key"."""
import io
import pathlib
import time

import av
import numpy as np
import pytest

from voice.config import REMOTE_TIMEOUT_S, SAMPLE_RATE, WHISPER_LOCAL_MODEL
from voice.engines import (AvDecoder, EnergySpeechFilter, FasterWhisperLocal, GroqRemote,
                           ProviderError, build_default_engines)
from voice.transcribe import (Engines, ProviderRateLimitError, TranscribeErrorCode,
                              TranscribeInputError, transcribe)


# --- Audio sintético y ayuda EBML
def wav_bytes(duration_s: int, sample_rate: int = 16000, bits: int = 16, channels: int = 1) -> bytes:
    byte_rate = sample_rate * channels * bits // 8
    data_size = byte_rate * duration_s
    fmt = ((1).to_bytes(2, "little") + channels.to_bytes(2, "little") + sample_rate.to_bytes(4, "little")
           + byte_rate.to_bytes(4, "little") + (channels * bits // 8).to_bytes(2, "little")
           + bits.to_bytes(2, "little"))
    return (b"RIFF" + (36 + data_size).to_bytes(4, "little") + b"WAVE" + b"fmt "
            + (16).to_bytes(4, "little") + fmt + b"data" + data_size.to_bytes(4, "little")
            + b"\x00" * data_size)


def encode_webm(duration_s: float, sample_rate: int = 48000, amplitude: float = 0.3) -> bytes:
    """Codifica un WebM/Opus en memoria: tono si amplitude > 0, silencio si es 0."""
    buffer = io.BytesIO()
    container = av.open(buffer, mode="w", format="webm")
    stream = container.add_stream("libopus", rate=sample_rate)
    stream.layout = "mono"
    total = int(duration_s * sample_rate)
    emitted = 0
    while emitted < total:
        n = min(sample_rate, total - emitted)
        t = np.arange(emitted, emitted + n, dtype="float32") / sample_rate
        wave = (amplitude * np.sin(2 * np.pi * 440.0 * t)).astype("float32").reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(wave, format="flt", layout="mono")
        frame.rate = sample_rate
        frame.pts = emitted
        for packet in stream.encode(frame):
            container.mux(packet)
        emitted += n
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    return buffer.getvalue()


def _vint_size(n: int) -> bytes:
    for length in range(1, 9):
        if n < (1 << (7 * length)) - 1:
            return (n | (1 << (7 * length))).to_bytes(length, "big")
    raise ValueError("vint too big")


def _element(data: bytes, pos: int):
    """(id_bytes, tamaño, inicio_cuerpo, fin_cuerpo) del elemento EBML en pos; tamaño None = desconocido."""
    id_len = 9 - data[pos].bit_length()
    elem_id = data[pos:pos + id_len]
    size_len = 9 - data[pos + id_len].bit_length()
    raw = data[pos + id_len:pos + id_len + size_len]
    mask = (1 << (7 * size_len)) - 1
    value = int.from_bytes(raw, "big") & mask
    body_start = pos + id_len + size_len
    known = value != mask
    return elem_id, (value if known else None), body_start, (body_start + value if known else len(data))


def strip_duration(data: bytes) -> bytes:
    """Quita Duration (0x4489) del Info de un WebM: duración desconocida, como MediaRecorder en streaming."""
    seg_id = b"\x18\x53\x80\x67"
    info_id = b"\x15\x49\xa9\x66"
    seg_pos = data.index(seg_id)
    seg_id_len = 9 - data[seg_pos].bit_length()
    _, seg_size, seg_body_start, seg_body_end = _element(data, seg_pos)
    info_pos = data.index(info_id, seg_body_start)
    _, info_size, info_body_start, info_body_end = _element(data, info_pos)
    info_body = bytearray(data[info_body_start:info_body_end])
    d_pos = info_body.index(b"\x44\x89")
    d_len = 9 - info_body[d_pos + 2].bit_length()
    d_size = int.from_bytes(info_body[d_pos + 2:d_pos + 2 + d_len], "big") & ((1 << (7 * d_len)) - 1)
    del info_body[d_pos:d_pos + 2 + d_len + d_size]
    new_info = info_id + _vint_size(len(info_body)) + bytes(info_body)
    saved = (info_body_end - info_pos) - len(new_info)
    body = data[seg_body_start:info_pos] + new_info + data[info_body_end:]
    if seg_size is not None:
        return data[:seg_pos] + seg_id + _vint_size(seg_size - saved) + body
    return data[:seg_body_start] + body


# --- Dobles
class FakeResponse:
    def __init__(self, status: int, body: bytes = b"{}", headers: dict | None = None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body


class FakeSegment:
    def __init__(self, text: str):
        self.text = text


class FakeWhisperModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, pcm, language=None):
        self.calls.append((pcm, language))
        return iter([FakeSegment(" Hola"), FakeSegment(" mundo")]), None


# --- Decodificador (spec: decodificado en memoria, una vez por turno, WebM/Opus y WAV)
def test_webm_sintetico_se_decodifica_a_pcm_16k_mono():
    webm = encode_webm(1.0)
    before = set(str(p) for p in pathlib.Path(".").iterdir())
    pcm = AvDecoder().decode(webm)
    assert set(str(p) for p in pathlib.Path(".").iterdir()) == before  # nada a disco
    assert isinstance(pcm, np.ndarray)
    assert pcm.ndim == 1
    assert pcm.dtype == np.float32
    assert 0.5 <= pcm.shape[0] / SAMPLE_RATE <= 1.5
    assert float(np.abs(pcm).max()) <= 1.0


def test_wav_sigue_funcionando_en_el_decodificador():
    pcm = AvDecoder().decode(wav_bytes(1))
    assert 0.9 <= pcm.shape[0] / SAMPLE_RATE <= 1.1
    assert pcm.dtype == np.float32


def test_bytes_basura_en_el_decodificador_es_invalid_audio():
    with pytest.raises(TranscribeInputError) as err:
        AvDecoder().decode(b"RIFFtrunc")
    assert err.value.code is TranscribeErrorCode.INVALID_AUDIO


def test_webm_de_60_s_es_too_long_por_cabecera_sin_decodificar():
    class CountingDecoder(AvDecoder):
        calls = 0

        def decode(self, audio):
            type(self).calls += 1
            return super().decode(audio)

    engines = Engines(decoder=CountingDecoder(), speech_filter=EnergySpeechFilter(),
                      remote=GroqRemote(), local=FasterWhisperLocal())
    with pytest.raises(TranscribeInputError) as err:
        transcribe(encode_webm(60.0, sample_rate=8000, amplitude=0.0), "req-1", False, engines)
    assert err.value.code is TranscribeErrorCode.AUDIO_TOO_LONG
    assert CountingDecoder.calls == 0


def test_webm_sin_duracion_que_supera_30_s_es_too_long_en_el_decodificador():
    webm = strip_duration(encode_webm(31.0, sample_rate=8000, amplitude=0.0))
    with pytest.raises(TranscribeInputError) as err:
        AvDecoder().decode(webm)
    assert err.value.code is TranscribeErrorCode.AUDIO_TOO_LONG


def test_webm_con_duracion_desconocida_corta_se_decodifica():
    webm = strip_duration(encode_webm(1.0, sample_rate=8000, amplitude=0.3))
    pcm = AvDecoder().decode(webm)
    assert 0.5 <= pcm.shape[0] / SAMPLE_RATE <= 1.5


# --- Filtro local de no-habla por energía
def test_filtro_silencio_es_false():
    silence = np.zeros(SAMPLE_RATE, dtype="float32")
    assert EnergySpeechFilter().has_speech(silence) is False


def test_filtro_tono_de_un_segundo_es_true():
    t = np.arange(SAMPLE_RATE, dtype="float32") / SAMPLE_RATE
    tone = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype("float32")
    assert EnergySpeechFilter().has_speech(tone) is True


def test_filtro_audio_mas_corto_que_la_minima_es_false():
    loud = np.full(int(SAMPLE_RATE * 0.05), 0.5, dtype="float32")
    assert EnergySpeechFilter().has_speech(loud) is False


def test_filtro_real_sobre_webm_cortado_con_tono_pasa():
    pcm = AvDecoder().decode(encode_webm(1.0))
    assert EnergySpeechFilter().has_speech(pcm) is True


def test_filtro_ruido_de_cuarto_es_false():
    # Cuarto de Sebastián: RMS 0,003 a 0,009 medido; se prueba con 0,012 para dejar margen (Whisper inventaba "Gracias.").
    ruido = np.random.default_rng(1).normal(0.0, 0.012, SAMPLE_RATE * 4).astype("float32")
    assert EnergySpeechFilter().has_speech(ruido) is False


def test_filtro_un_clic_corto_en_silencio_es_false():
    # El ESPACIO que detiene la grabación suena como un golpe de ~40 ms: no es habla.
    audio = np.zeros(SAMPLE_RATE * 4, dtype="float32")
    audio[SAMPLE_RATE:SAMPLE_RATE + int(SAMPLE_RATE * 0.04)] = 0.9
    assert EnergySpeechFilter().has_speech(audio) is False


def test_filtro_habla_corta_entre_silencios_es_true():
    audio = np.random.default_rng(2).normal(0.0, 0.005, SAMPLE_RATE * 4).astype("float32")
    t = np.arange(SAMPLE_RATE, dtype="float32") / SAMPLE_RATE
    audio[SAMPLE_RATE:SAMPLE_RATE * 2] += (0.08 * np.sin(2 * np.pi * 220.0 * t)).astype("float32")
    assert EnergySpeechFilter().has_speech(audio) is True


def test_filtro_ruido_normalizado_a_pico_uno_tampoco_pasa_si_no_hay_tramo_largo():
    # Un clic en un cuarto ruidoso, normalizado al pico, no debe contar como un tramo de habla.
    audio = np.random.default_rng(3).normal(0.0, 0.003, SAMPLE_RATE * 4).astype("float32")
    audio[SAMPLE_RATE:SAMPLE_RATE + 320] = 0.5
    assert EnergySpeechFilter().has_speech(audio) is False


# --- Groq (urllib con monkeypatch: sin red real)
def test_groq_200_devuelve_el_texto(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("voice.engines._urlopen",
                        lambda request, timeout=None: FakeResponse(200, b'{"text": "hola"}'))
    pcm = np.zeros(SAMPLE_RATE, dtype="float32")
    assert GroqRemote().transcribe(pcm) == "hola"


def test_groq_multipart_lleva_model_language_y_archivo(monkeypatch):
    sent = {}
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fake_urlopen(request, timeout=None):
        sent["request"] = request
        sent["timeout"] = timeout
        return FakeResponse(200, b'{"text": "ok"}')

    monkeypatch.setattr("voice.engines._urlopen", fake_urlopen)
    pcm = np.full(SAMPLE_RATE, 0.1, dtype="float32")
    GroqRemote().transcribe(pcm)
    request = sent["request"]
    body = request.data
    assert sent["timeout"] == REMOTE_TIMEOUT_S
    assert b'name="model"' in body and b"whisper-large-v3-turbo" in body
    assert b'name="language"' in body and b"\r\nes\r\n" in body
    assert b'name="file"' in body
    file_part = body.split(b'name="file"', 1)[1]
    assert b"WAVE" in file_part                       # el PCM viaja como WAV en memoria
    assert len(file_part.split(b"WAVEfmt ", 1)[1]) > 2 * SAMPLE_RATE
    assert request.get_header("Authorization") == "Bearer test-key"
    assert "multipart/form-data" in (request.get_header("Content-type") or "")


def test_groq_429_con_retry_after(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("voice.engines._urlopen",
                        lambda request, timeout=None: FakeResponse(429, headers={"retry-after": "7"}))
    with pytest.raises(ProviderRateLimitError) as err:
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))
    assert err.value.retry_after_s == 7


def test_groq_429_por_httperror_con_retry_after(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fake(request, timeout=None):
        raise urllib.error.HTTPError("https://api.groq.com", 429, "slow down", {"retry-after": "3"}, None)

    monkeypatch.setattr("voice.engines._urlopen", fake)
    with pytest.raises(ProviderRateLimitError) as err:
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))
    assert err.value.retry_after_s == 3


def test_groq_500_y_timeout_son_fallo_del_proveedor(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fake_500(request, timeout=None):
        raise urllib.error.HTTPError("https://api.groq.com", 500, "boom", {}, None)

    monkeypatch.setattr("voice.engines._urlopen", fake_500)
    with pytest.raises(ProviderError):
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))

    def fake_timeout(request, timeout=None):
        raise TimeoutError()

    monkeypatch.setattr("voice.engines._urlopen", fake_timeout)
    with pytest.raises(ProviderError):
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))


def test_groq_sin_llave_es_fallo_del_proveedor(monkeypatch):
    calls = []

    def fake(request, timeout=None):
        calls.append(request)
        return FakeResponse(200, b'{"text": "x"}')

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr("voice.engines._urlopen", fake)
    with pytest.raises(ProviderError):
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))
    assert calls == []          # ni siquiera intenta la red


def test_la_llave_nunca_aparece_en_los_errores(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fake(request, timeout=None):
        raise urllib.error.HTTPError("https://api.groq.com", 500, "boom", {}, None)

    monkeypatch.setattr("voice.engines._urlopen", fake)
    try:
        GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))
        raise AssertionError("debía fallar")
    except ProviderError as err:
        assert "test-key" not in str(err)
        assert "test-key" not in repr(err)


def test_groq_200_devuelve_el_texto_del_json(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr("voice.engines._urlopen",
                        lambda request, timeout=None: FakeResponse(200, b'{"text": "no"}'))
    assert GroqRemote().transcribe(np.zeros(SAMPLE_RATE, dtype="float32")) == "no"


# --- Respaldo local faster-whisper (doble inyectado, sin descargar el modelo)
def test_local_une_los_segmentos_en_espanol():
    models = []

    def factory(name, **options):
        model = FakeWhisperModel()
        models.append((name, options, model))
        return model

    local = FasterWhisperLocal(model_factory=factory)
    assert models == []                      # la carga es perezosa: nada al construir
    pcm = np.zeros(SAMPLE_RATE, dtype="float32")
    assert local.transcribe(pcm) == "Hola mundo"
    assert local.transcribe(pcm) == "Hola mundo"
    assert len(models) == 1                  # la carga ocurre una sola vez
    assert models[0][0] == WHISPER_LOCAL_MODEL
    assert models[0][1] == {"device": "cpu", "compute_type": "int8"}
    assert models[0][2].calls == [(pcm, "es"), (pcm, "es")]


def test_local_falla_y_la_excepcion_sube():
    def factory(name, **options):
        def boom(pcm, language=None):
            raise RuntimeError("whisper local failed")

        return type("M", (), {"transcribe": staticmethod(boom)})()

    local = FasterWhisperLocal(model_factory=factory)
    with pytest.raises(RuntimeError):
        local.transcribe(np.zeros(SAMPLE_RATE, dtype="float32"))


# --- Fábrica
def test_fabrica_cablea_los_motores_reales():
    engines = build_default_engines()
    assert isinstance(engines.decoder, AvDecoder)
    assert isinstance(engines.speech_filter, EnergySpeechFilter)
    assert isinstance(engines.remote, GroqRemote)
    assert isinstance(engines.local, FasterWhisperLocal)
    assert engines.sleep is time.sleep
    assert engines.local._model is None      # perezosa: nada se descarga al construir