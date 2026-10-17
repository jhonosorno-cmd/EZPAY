"""Escenarios del umbral: "Misma persona pasa el umbral", "En el borde
(score == 0.45)" y "Otra persona no pasa el umbral" (speaker-verification).

La comparación es en el borde: `score >= umbral` ⇒ VERIFIED.
"""
import tempfile
import unittest

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import (EmbedderFalso, EmbedderFijo, F_DUEÑO, F_IMPOSTOR,
                              tono, vector_en)


class MismaPersonaPasaElUmbral(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0, umbral=0.45)
        self.verifier.load()
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)

    def tearDown(self):
        self.temporal.cleanup()

    def test_la_voz_del_usuario_enrolado_es_verified(self):
        resultado = self.verifier.verify(tono(F_DUEÑO), user="usuario")
        self.assertEqual(resultado["status"], "VERIFIED")
        self.assertGreaterEqual(resultado["score"], 0.45)
        self.assertIsInstance(resultado["score"], float)


class EnElBorde(unittest.TestCase):
    def test_score_exactamente_igual_al_umbral_es_verified(self):
        # La huella es [1, 0, ...]; el comando devuelve un vector con coseno conocido contra ella.
        comando = vector_en(1.1040301)  # arccos(0.45) ≈ 1.1040298
        temporal = tempfile.TemporaryDirectory()
        try:
            import numpy as np

            huella = np.zeros(8, dtype="float32")
            huella[0] = 1.0
            store = SpeakerStore(temporal.name)
            al_enrolar = SpeakerVerifier(embedder=EmbedderFijo(huella), store=store,
                                         min_verify_seconds=2.0, umbral=0.45)
            al_enrolar.load()
            SpeakerEnrollment(al_enrolar).enroll([tono(150.0)] * 3, consent=True)

            # 1) con umbral alto: mide el score sin aceptar
            medidor = SpeakerVerifier(embedder=EmbedderFijo(comando), store=store,
                                      min_verify_seconds=2.0, umbral=2.0)
            medidor.load()
            score = medidor.verify(tono(150.0), user="usuario")["score"]
            self.assertEqual(medidor.verify(tono(150.0), user="usuario")["status"], "BELOW_THRESHOLD")
            # 2) umbral == score exacto: el borde entra con >=
            al_borde = SpeakerVerifier(embedder=EmbedderFijo(comando), store=store,
                                       min_verify_seconds=2.0, umbral=score)
            al_borde.load()
            resultado = al_borde.verify(tono(150.0), user="usuario")
            self.assertEqual(resultado["score"], score)
            self.assertEqual(resultado["status"], "VERIFIED")
            self.assertAlmostEqual(resultado["score"], 0.45, delta=1e-3)
        finally:
            temporal.cleanup()


class OtraPersonaNoPasaElUmbral(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0, umbral=0.45)
        self.verifier.load()
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)

    def tearDown(self):
        self.temporal.cleanup()

    def test_la_voz_de_otra_persona_es_below_threshold(self):
        resultado = self.verifier.verify(tono(F_IMPOSTOR), user="usuario")
        self.assertEqual(resultado["status"], "BELOW_THRESHOLD")
        self.assertLess(resultado["score"], 0.45)
        self.assertIsInstance(resultado["score"], float)


if __name__ == "__main__":
    unittest.main()