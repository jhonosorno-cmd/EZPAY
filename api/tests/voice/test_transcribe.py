"""Pruebas de speech-transcription: una por escenario de
openspec/changes/add-voice-understanding/specs/speech-transcription/spec.md, más entradas hostiles y las
reglas estructurales (solo librería estándar, sin disco, sin red, sin llaves, sin logs, sin float).
El audio es sintético: cabeceras WAV generadas aquí, nunca archivos ni audio real. Los motores son dobles
de prueba que registran sus llamadas; su contenido no importa en Fase 1."""
import ast
import importlib
import sys
from pathlib import Path

import pytest

from voice.config import TURN_BUDGET_S
from voice.transcribe import (Decoder, Engine, Engines, LocalEngine, ProviderRateLimitError,
                              RemoteEngine, SpeechFilter, Transcript, TranscribeErrorCode,
                              TranscribeInputError, transcribe)

COMMAND_TEXT = "envíale veinte mil a mi hija"


# --- Audio sintético y dobles de prueba
def wav_bytes(duration_s: int, sample_rate: int = 16000, bits: int = 16, channels: int = 1,
              with_payload: bool = True) -> bytes:
    """Cabecera WAV (RIFF) coherente; el contenido nunca se decodifica en estas pruebas."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = byte_rate * duration_s
    fmt = ((1).to_bytes(2, "little") + channels.to_bytes(2, "little") + sample_rate.to_bytes(4, "little")
           + byte_rate.to_bytes(4, "little") + block_align.to_bytes(2, "little") + bits.to_bytes(2, "little"))
    out = (b"RIFF" + (36 + data_size).to_bytes(4, "little") + b"WAVE" + b"fmt "
           + (16).to_bytes(4, "little") + fmt + b"data" + data_size.to_bytes(4, "little"))
    return out + (b"\x00" * data_size if with_payload else b"")


class FakeDecoder(Decoder):
    def __init__(self):
        self.calls = 0
        self.received = []
        self.pcm = object()

    def decode(self, audio):
        self.calls += 1
        self.received.append(audio)
        return self.pcm


class FakeFilter(SpeechFilter):
    def __init__(self, has_speech):
        self.has = has_speech
        self.calls = 0
        self.received = []

    def has_speech(self, pcm):
        self.calls += 1
        self.received.append(pcm)
        return self.has


class FakeRemote(RemoteEngine):
    def __init__(self, text=COMMAND_TEXT, errors=()):
        self.text = text
        self.errors = list(errors)
        self.calls = 0
        self.received = []

    def transcribe(self, pcm):
        self.calls += 1
        self.received.append(pcm)
        if self.errors:
            raise self.errors.pop(0)
        return self.text


class FakeLocal(LocalEngine):
    def __init__(self, text=COMMAND_TEXT):
        self.text = text
        self.calls = 0
        self.received = []

    def transcribe(self, pcm):
        self.calls += 1
        self.received.append(pcm)
        return self.text


class FakeSleep:
    def __init__(self):
        self.naps = []

    def __call__(self, seconds):
        self.naps.append(seconds)


def make_engines(has_speech=True, remote=None, local=None, decoder=None, sleep=None) -> Engines:
    return Engines(decoder=decoder or FakeDecoder(), speech_filter=FakeFilter(has_speech),
                   remote=remote or FakeRemote(), local=local or FakeLocal(), sleep=sleep)


# --- Escenarios del spec: consentimiento
def test_con_consentimiento_envia_al_proveedor():
    remote = FakeRemote()
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote))
    assert result.text == COMMAND_TEXT
    assert result.had_speech is True
    assert result.engine is Engine.GROQ
    assert remote.calls == 1


def test_sin_consentimiento_transcribe_local_y_sin_conexiones():
    remote = FakeRemote()
    local = FakeLocal(text=COMMAND_TEXT)
    result = transcribe(wav_bytes(2), "req-1", False, make_engines(remote=remote, local=local))
    assert result.engine is Engine.LOCAL
    assert result.text == COMMAND_TEXT
    assert remote.calls == 0


def test_proveedor_supera_su_plazo_y_falla_a_local():
    remote = FakeRemote(errors=[TimeoutError()])
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote))
    assert result.engine is Engine.LOCAL
    assert result.had_speech is True


def test_proveedor_devuelve_error_y_falla_a_local():
    remote = FakeRemote(errors=[RuntimeError("500")])
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote))
    assert result.engine is Engine.LOCAL


# --- Escenarios del spec: límite de uso
def test_limite_excedido_con_retry_after_largo_va_a_local():
    sleeper = FakeSleep()
    remote = FakeRemote(errors=[ProviderRateLimitError(retry_after_s=TURN_BUDGET_S + 1)])
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote, sleep=sleeper))
    assert result.engine is Engine.LOCAL
    assert sleeper.naps == []
    assert remote.calls == 1


def test_limite_excedido_con_retry_after_corto_se_respeta_y_reintenta():
    sleeper = FakeSleep()
    remote = FakeRemote(errors=[ProviderRateLimitError(retry_after_s=2)])
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote, sleep=sleeper))
    assert sleeper.naps == [2]
    assert remote.calls == 2
    assert result.engine is Engine.GROQ


def test_limite_excedido_y_reintento_fallido_va_a_local():
    remote = FakeRemote(errors=[ProviderRateLimitError(retry_after_s=1), TimeoutError()])
    result = transcribe(wav_bytes(2), "req-1", True, make_engines(remote=remote, sleep=FakeSleep()))
    assert result.engine is Engine.LOCAL


# --- Escenarios del spec: silencio y ruido
def test_audio_en_silencio_no_llama_a_ningun_motor():
    remote = FakeRemote()
    local = FakeLocal()
    result = transcribe(wav_bytes(4), "req-1", True,
                        make_engines(has_speech=False, remote=remote, local=local))
    assert result == Transcript(text="", had_speech=False, engine=Engine.NONE, transcript_confidence=None)
    assert remote.calls == 0
    assert local.calls == 0


def test_ruido_de_sala_transcripcion_vacia():
    result = transcribe(wav_bytes(4), "req-1", True, make_engines(has_speech=False))
    assert result.text == ""
    assert result.had_speech is False
    assert result.engine is Engine.NONE


def test_motor_que_inventaria_texto_sobre_silencio():
    remote = FakeRemote(text="Gracias.")
    result = transcribe(wav_bytes(4), "req-1", True, make_engines(has_speech=False, remote=remote))
    assert result.text == ""
    assert remote.calls == 0


def test_silencio_con_vocabulario_guia_nunca_llega_al_proveedor():
    remote = FakeRemote(text="Laura")
    result = transcribe(wav_bytes(4), "req-1", True, make_engines(has_speech=False, remote=remote))
    assert result.text == ""
    assert remote.calls == 0


def test_respuesta_corta_de_una_silaba_pasa_el_filtro():
    local = FakeLocal(text="no")
    result = transcribe(wav_bytes(1), "req-1", False, make_engines(has_speech=True, local=local))
    assert result.text == "no"
    assert result.engine is Engine.LOCAL
    assert local.calls == 1


# --- Escenarios del spec: decodificado, confianza y validación de entrada
def test_un_solo_decodificado_y_mismo_buffer():
    decoder = FakeDecoder()
    remote = FakeRemote()
    audio = wav_bytes(2)
    result = transcribe(audio, "req-1", True, make_engines(decoder=decoder, remote=remote))
    assert result.had_speech is True
    assert decoder.calls == 1
    assert decoder.received == [audio]
    assert remote.received == [decoder.pcm]


def test_transcript_confidence_null_y_to_dict_camelcase():
    result = transcribe(wav_bytes(2), "req-1", True, make_engines())
    assert result.transcript_confidence is None
    assert result.to_dict() == {"text": COMMAND_TEXT, "hadSpeech": True, "engine": "groq",
                                "transcriptConfidence": None}
    silence = transcribe(wav_bytes(4), "req-1", True, make_engines(has_speech=False))
    assert silence.to_dict() == {"text": "", "hadSpeech": False, "engine": "none",
                                 "transcriptConfidence": None}


def test_audio_de_60_s_es_too_long_solo_con_la_cabecera():
    decoder = FakeDecoder()
    with pytest.raises(TranscribeInputError) as err:
        transcribe(wav_bytes(60, with_payload=False), "req-1", False,
                   make_engines(decoder=decoder))
    assert err.value.code is TranscribeErrorCode.AUDIO_TOO_LONG
    assert decoder.calls == 0


def test_audio_de_30_s_exacto_pasa_la_validacion():
    decoder = FakeDecoder()
    result = transcribe(wav_bytes(30, sample_rate=2, bits=8), "req-1", False,
                        make_engines(decoder=decoder, has_speech=False))
    assert result.engine is Engine.NONE
    assert decoder.calls == 1


def test_bytes_basura_es_invalid_audio_sin_decodificar():
    decoder = FakeDecoder()
    with pytest.raises(TranscribeInputError) as err:
        transcribe(b"\x1f\x8b\x08garbage-not-audio\x00", "req-1", True, make_engines(decoder=decoder))
    assert err.value.code is TranscribeErrorCode.INVALID_AUDIO
    assert decoder.calls == 0


def test_audio_vacio_es_invalid_audio():
    decoder = FakeDecoder()
    with pytest.raises(TranscribeInputError) as err:
        transcribe(b"", "req-1", True, make_engines(decoder=decoder))
    assert err.value.code is TranscribeErrorCode.INVALID_AUDIO
    assert decoder.calls == 0


@pytest.mark.parametrize("bad", ["RIFF...", None, 123, ["RIFF"], bytearray(b"RIFF")])
def test_entradas_que_no_son_bytes_es_invalid_audio(bad):
    with pytest.raises(TranscribeInputError) as err:
        transcribe(bad, "req-1", True, make_engines())
    assert err.value.code is TranscribeErrorCode.INVALID_AUDIO


@pytest.mark.parametrize("bad_id", ["", "   ", None, 123])
def test_request_id_vacio_o_no_valido(bad_id):
    with pytest.raises(ValueError):
        transcribe(wav_bytes(2), bad_id, True, make_engines())


# --- Reglas estructurales del módulo (ast)
def _transcribe_source() -> str:
    return Path(importlib.import_module("voice.transcribe").__file__).read_text(encoding="utf-8")


def _transcribe_tree():
    return ast.parse(_transcribe_source())


def test_transcribe_solo_importa_la_libreria_estandar():
    allowed = set(sys.stdlib_module_names) | {"voice"}
    for node in ast.walk(_transcribe_tree()):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        else:
            continue
        for mod in mods:
            assert mod.split(".")[0] in allowed, f"transcribe importa {mod}: fuera de la librería estándar"


def test_transcribe_sin_disco_ni_red_ni_logs_ni_llaves():
    assert "GROQ_API_KEY" not in _transcribe_source()
    for node in ast.walk(_transcribe_tree()):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert "logging" not in mods
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "stdout", "stderr"}, node.attr
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            assert name not in {"open", "write", "write_text", "write_bytes", "print", "getenv"}, name


def test_transcribe_sin_float_ni_dinero():
    for node in ast.walk(_transcribe_tree()):
        assert not (isinstance(node, ast.Name) and node.id in {"float", "round", "Decimal"})
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float))
        assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div))