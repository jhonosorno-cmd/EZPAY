"""Scenario "La salida es el context.voice del motor" y "Primer comando sin espera de carga".

speaker-verification: `verify(pcm, user) -> {status, score}` es exactamente el
`context.voice` que consume el motor; el modelo carga una sola vez al arrancar.
"""
import tempfile
import unittest

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import EmbedderFalso, F_DUEÑO, tono


class LaSalidaEsElContextVoiceDelMotor(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.store = SpeakerStore(self.temporal.name)
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=self.store, min_verify_seconds=2.0)
        self.verifier.load()

    def tearDown(self):
        self.temporal.cleanup()

    def test_verify_devuelve_exactamente_status_y_score(self):
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
        resultado = self.verifier.verify(tono(F_DUEÑO), user="usuario")
        self.assertEqual(set(resultado.keys()), {"status", "score"})
        self.assertIn(resultado["status"], {"VERIFIED", "BELOW_THRESHOLD", "NOT_AVAILABLE"})
        if resultado["status"] == "NOT_AVAILABLE":
            self.assertIsNone(resultado["score"])
        else:
            self.assertIsInstance(resultado["score"], float)


class PrimerComandoSinEsperaDeCarga(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.embedder = EmbedderFalso()
        self.verifier = SpeakerVerifier(embedder=self.embedder, store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)

    def tearDown(self):
        self.temporal.cleanup()

    def test_el_modelo_carga_en_load_y_no_en_la_primera_peticion(self):
        self.assertEqual(self.embedder.cargas, 0)  # nada de carga perezosa antes de arrancar
        self.verifier.load()
        self.assertEqual(self.embedder.cargas, 1)
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
        self.verifier.verify(tono(F_DUEÑO), user="usuario")
        self.verifier.verify(tono(F_DUEÑO), user="usuario")
        self.assertEqual(self.embedder.cargas, 1)  # ni la primera ni la segunda petición cargan


if __name__ == "__main__":
    unittest.main()