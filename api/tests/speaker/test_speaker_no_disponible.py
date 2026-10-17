"""Escenarios NOT_AVAILABLE de speaker-verification (fallo cerrado, SEG-6).

"Modelo que no carga ⇒ NOT_AVAILABLE", "Audio de más de 30 s", "Clip demasiado
corto", "Usuario no enrolado" y "Error interno del modelo".
"""
import tempfile
import unittest

from speaker import SpeakerStore, SpeakerVerifier, duracion_voz_util
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import EmbedderFalso, F_DUEÑO, tono


class ModeloQueNoCarga(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(fallo_al_cargar=True),
                                        store=SpeakerStore(self.temporal.name), min_verify_seconds=2.0)
        with self.assertLogs("speaker", level="WARNING") as self.captura:
            self.verifier.load()  # el arranque falla y queda el aviso

    def tearDown(self):
        self.temporal.cleanup()

    def test_toda_verificacion_devuelve_not_available(self):
        for pcm in (tono(F_DUEÑO), tono(700.0)):
            resultado = self.verifier.verify(pcm, user="usuario")
            self.assertEqual(resultado, {"status": "NOT_AVAILABLE", "score": None})

    def test_el_aviso_del_arranque_no_lleva_datos_biometricos(self):
        self.assertTrue(any("failed to load" in mensaje for mensaje in self.captura.output))
        for mensaje in self.captura.output:
            self.assertNotIn("score", mensaje.lower())
            self.assertLess(len(mensaje), 200)  # nada de audio ni arrays


class AudioDeMasDe30Segundos(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.embedder = EmbedderFalso()
        self.verifier = SpeakerVerifier(embedder=self.embedder, store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        self.verifier.load()

    def tearDown(self):
        self.temporal.cleanup()

    def test_no_se_carga_el_audio_en_el_modelo(self):
        pcm_largo = tono(F_DUEÑO, segundos=31.0, silencio_inicial=0.0, silencio_final=0.0)
        self.assertGreater(pcm_largo.size / 16000.0, 30.0)
        self.assertEqual(self.verifier.verify(pcm_largo, user="usuario"),
                         {"status": "NOT_AVAILABLE", "score": None})
        self.assertEqual(self.embedder.llamadas, 0)  # defensa en profundidad: no entra al modelo

    def test_embed_tampoco_procesa_mas_de_30_segundos(self):
        pcm_largo = tono(F_DUEÑO, segundos=31.0, silencio_inicial=0.0, silencio_final=0.0)
        self.assertIsNone(self.verifier.embed(pcm_largo))
        self.assertEqual(self.embedder.llamadas, 0)  # no se recorta: no se procesa


class ClipDemasiadoCorto(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.embedder = EmbedderFalso()
        self.verifier = SpeakerVerifier(embedder=self.embedder, store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        self.verifier.load()
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)

    def tearDown(self):
        self.temporal.cleanup()

    def test_un_comando_con_menos_de_min_verify_seconds_devuelve_not_available(self):
        corto = tono(F_DUEÑO, segundos=4.0, silencio_inicial=1.5, silencio_final=1.5)  # voz útil 1,0 s
        self.assertEqual(self.verifier.verify(corto, user="usuario"),
                         {"status": "NOT_AVAILABLE", "score": None})


class UsuarioNoEnrolado(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        self.verifier.load()

    def tearDown(self):
        self.temporal.cleanup()

    def test_sin_huella_devuelve_not_available(self):
        self.assertEqual(self.verifier.verify(tono(F_DUEÑO), user="nadie"),
                         {"status": "NOT_AVAILABLE", "score": None})


class LaCalibracionMideConElMargen(unittest.TestCase):
    """No-regresión (desviación 1): la toma de la demo mide 2,06–3,02 s CON el
    margen de 0,25 s; una voz de 1,6 s mide 2,1 s ⇒ VERIFIED, no NOT_AVAILABLE.
    Medir sin margen daría ~1,6 s ⇒ PIN en plena demo."""

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        self.verifier.load()
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)

    def tearDown(self):
        self.temporal.cleanup()

    def test_una_toma_con_1_6_segundos_de_voz_se_verifica(self):
        toma = tono(F_DUEÑO, segundos=2.1, silencio_inicial=0.25, silencio_final=0.25)  # voz útil 1,6 s
        self.assertAlmostEqual(duracion_voz_util(toma), 2.1, delta=1e-9)
        self.assertEqual(self.verifier.verify(toma, user="usuario")["status"], "VERIFIED")

    def test_una_toma_con_1_4_segundos_de_voz_da_not_available(self):
        toma = tono(F_DUEÑO, segundos=1.9, silencio_inicial=0.25, silencio_final=0.25)  # voz útil 1,4 s
        self.assertAlmostEqual(duracion_voz_util(toma), 1.9, delta=1e-9)
        self.assertEqual(self.verifier.verify(toma, user="usuario"),
                         {"status": "NOT_AVAILABLE", "score": None})


class ErrorInternoDelModelo(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.embedder = EmbedderFalso()
        self.verifier = SpeakerVerifier(embedder=self.embedder, store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        self.verifier.load()
        SpeakerEnrollment(self.verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
        self.embedder.fallo_al_embed = True  # el modelo se rompe DESPUÉS del enrolamiento

    def tearDown(self):
        self.temporal.cleanup()

    def test_un_fallo_del_modelo_devuelve_not_available_nunca_verified(self):
        self.assertEqual(self.verifier.verify(tono(F_DUEÑO), user="usuario"),
                         {"status": "NOT_AVAILABLE", "score": None})


if __name__ == "__main__":
    unittest.main()