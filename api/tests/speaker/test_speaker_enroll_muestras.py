"""Escenarios de voice-enrollment: muestras y errores (B-5).

"Faltan muestras", "Tres muestras válidas", "Muestra vacía o demasiado
corta", "Muestra de más de 15 s" y "Muestra de 4 s con 2 s de silencio"
(duración medida DESPUÉS del recorte).
"""
import tempfile
import unittest

from speaker import SpeakerStore, SpeakerVerifier, duracion_voz_util
from speaker.enrollment import EnrollmentError, SpeakerEnrollment
from speaker_fixtures import EmbedderFalso, F_DUEÑO, tono


class EnrollBase(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.embedder = EmbedderFalso()
        self.enrollment = SpeakerEnrollment(
            SpeakerVerifier(embedder=self.embedder, store=SpeakerStore(self.temporal.name),
                            min_verify_seconds=2.0))
        self.enrollment.verifier.load()  # el modelo carga al arrancar, como en producción

    def tearDown(self):
        self.temporal.cleanup()


class FaltanMuestras(EnrollBase):
    def test_dos_muestras_responden_samples_required(self):
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO)] * 2, consent=True)
        self.assertEqual(captura.exception.code, "SAMPLES_REQUIRED")
        self.assertEqual(self.enrollment.status(), {"enrolled": False})

    def test_cuatro_muestras_tambien_responden_samples_required(self):
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO)] * 4, consent=True)
        self.assertEqual(captura.exception.code, "SAMPLES_REQUIRED")


class TresMuestrasValidas(EnrollBase):
    def test_tres_muestras_consistentes_crean_la_huella(self):
        resultado = self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        self.assertEqual(resultado, {"enrolled": True})
        self.assertEqual(self.enrollment.status(), {"enrolled": True})


class MuestraVaciaODemasiadoCorta(EnrollBase):
    def test_muestra_vacia_responde_invalid_audio(self):
        import numpy as np

        vacia = np.zeros(0, dtype="float32")
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), vacia], consent=True)
        self.assertEqual(captura.exception.code, "INVALID_AUDIO")
        self.assertEqual(self.enrollment.status(), {"enrolled": False})

    def test_muestra_solo_silencio_es_ilegible(self):
        silencio = tono(F_DUEÑO, segundos=4.0, silencio_inicial=2.0, silencio_final=2.0)
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), silencio], consent=True)
        self.assertEqual(captura.exception.code, "INVALID_AUDIO")

    def test_muestra_con_menos_de_3_segundos_de_voz_util(self):
        corto = tono(F_DUEÑO, segundos=3.0, silencio_inicial=0.5, silencio_final=0.5)
        # voz útil 2,0 s; con el margen de calibración mide 2,5 s < 3 s
        self.assertAlmostEqual(duracion_voz_util(corto), 2.5, delta=1e-9)
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), corto], consent=True)
        self.assertEqual(captura.exception.code, "INVALID_AUDIO")


class MuestraDeMasDe15Segundos(EnrollBase):
    def test_voz_util_de_16_segundos_responde_invalid_audio(self):
        largo = tono(F_DUEÑO, segundos=18.0, silencio_inicial=1.0, silencio_final=1.0)
        # voz útil 16 s; con el margen mide 16,5 s > 15 s
        self.assertAlmostEqual(duracion_voz_util(largo), 16.5, delta=1e-9)
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), largo], consent=True)
        self.assertEqual(captura.exception.code, "INVALID_AUDIO")
        self.assertEqual(self.enrollment.status(), {"enrolled": False})


class MuestraDe4SegundosCon2SegundosDeSilencio(EnrollBase):
    def test_la_duracion_se_mide_despues_del_recorte(self):
        # 4 s totales pero solo 2 s de voz útil; con el margen de calibración mide 2,5 s < 3 s
        muestra = tono(F_DUEÑO, segundos=4.0, silencio_inicial=1.0, silencio_final=1.0)
        self.assertEqual(muestra.size / 16000.0, 4.0)  # dura 4 s en crudo
        self.assertAlmostEqual(duracion_voz_util(muestra), 2.5, delta=1e-9)
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), muestra], consent=True)
        self.assertEqual(captura.exception.code, "INVALID_AUDIO")


if __name__ == "__main__":
    unittest.main()