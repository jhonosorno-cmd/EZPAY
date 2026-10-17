"""Modo EZPAY_STT_PROVIDER=groq: Groq primero, sin depender del consentimiento; si falla, respaldo local."""
import unittest
from unittest import mock

from app.voice_io import VoiceIO
from voice.config import REMOTE_TIMEOUT_S
from voice.transcribe import Engine, Engines


class _Decoder:
    def decode(self, audio):
        return audio


class _Speech:
    def has_speech(self, pcm):
        return True


class _Remote:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def transcribe(self, pcm):
        self.calls += 1
        if self.fail:
            raise RuntimeError("proveedor caído")
        return "envíale veinte mil a laura"


class _Local:
    def __init__(self):
        self.calls = 0

    def transcribe(self, pcm):
        self.calls += 1
        return "local"


def voice_io(remote, local):
    io = VoiceIO(engines=Engines(_Decoder(), _Speech(), remote, local), stt_provider="groq")
    return io


class _Mp4Decoder:
    def __init__(self):
        self.seen = []

    def decode(self, audio):
        self.seen.append(audio[:12])
        import numpy as np
        return np.zeros(1600, dtype="float32")


class SafariAudioTest(unittest.TestCase):
    def test_mp4_is_repacked_to_wav_before_validation(self):
        decoder, remote = _Mp4Decoder(), _Remote()
        io = VoiceIO(engines=Engines(decoder, _Speech(), remote, _Local()), stt_provider="groq")
        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
        transcript, _ = io.transcribe_command(mp4, "rid-mp4", verify=False)
        self.assertEqual(transcript.engine, Engine.GROQ)
        self.assertEqual(decoder.seen[0][4:8], b"ftyp")      # se decodificó el mp4 original
        self.assertEqual(decoder.seen[1][:4], b"RIFF")       # y el transcriptor recibió WAV


class GroqOnlyTest(unittest.TestCase):
    def test_groq_is_used_without_enrollment_consent(self):
        remote = _Remote()
        transcript, _ = voice_io(remote, _Local()).transcribe_command(b"\x1a\x45\xdf\xa3", "rid-1", verify=False)
        self.assertEqual(transcript.engine, Engine.GROQ)
        self.assertEqual(remote.calls, 1)

    def test_groq_failure_falls_back_to_local(self):
        remote, local = _Remote(fail=True), _Local()
        transcript, _ = voice_io(remote, local).transcribe_command(b"\x1a\x45\xdf\xa3", "rid-2", verify=False)
        self.assertEqual(transcript.engine, Engine.LOCAL)
        self.assertEqual(transcript.text, "local")
        self.assertEqual(local.calls, 1)

    def test_load_keeps_the_real_local_engine_in_groq_mode(self):
        local = _Local()
        built = Engines(_Decoder(), _Speech(), _Remote(fail=True), local)
        io = VoiceIO(stt_provider="groq", verifier=object())
        with mock.patch("voice.engines.build_default_engines", return_value=built):
            io.load()
        transcript, _ = io.transcribe_command(b"\x1a\x45\xdf\xa3", "rid-load", verify=False)
        self.assertEqual(transcript.engine, Engine.LOCAL)

    def test_groq_gets_six_seconds_before_the_fallback(self):
        self.assertEqual(REMOTE_TIMEOUT_S, 6)

    def test_auto_mode_keeps_the_local_fallback(self):
        local = _Local()
        io = VoiceIO(engines=Engines(_Decoder(), _Speech(), _Remote(fail=True), local), stt_provider="auto")
        transcript, _ = io.transcribe_command(b"\x1a\x45\xdf\xa3", "rid-3", verify=False)
        self.assertEqual(transcript.engine, Engine.LOCAL)


if __name__ == "__main__":
    unittest.main()
