"""Modo EZPAY_STT_PROVIDER=groq: la transcripción va siempre a Groq y nunca al whisper local."""
import unittest

from app.voice_io import RemoteSttFailed, VoiceIO, _LocalDisabled
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


class GroqOnlyTest(unittest.TestCase):
    def test_groq_is_used_without_enrollment_consent(self):
        remote = _Remote()
        transcript, _ = voice_io(remote, _Local()).transcribe_command(b"\x1a\x45\xdf\xa3", "rid-1", verify=False)
        self.assertEqual(transcript.engine, Engine.GROQ)
        self.assertEqual(remote.calls, 1)

    def test_groq_failure_never_falls_back_to_local(self):
        with self.assertRaises(RemoteSttFailed):
            voice_io(_Remote(fail=True), _LocalDisabled()).transcribe_command(b"\x1a\x45\xdf\xa3", "rid-2", verify=False)

    def test_auto_mode_keeps_the_local_fallback(self):
        local = _Local()
        io = VoiceIO(engines=Engines(_Decoder(), _Speech(), _Remote(fail=True), local), stt_provider="auto")
        transcript, _ = io.transcribe_command(b"\x1a\x45\xdf\xa3", "rid-3", verify=False)
        self.assertEqual(transcript.engine, Engine.LOCAL)


if __name__ == "__main__":
    unittest.main()
