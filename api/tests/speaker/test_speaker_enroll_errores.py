"""Escenarios de voice-enrollment: consistencia entre muestras y orden de errores.

"Muestras consistentes", "Muestras de dos personas" (INCONSISTENT_SAMPLES),
"Varios errores a la vez" (orden CONSENT_REQUIRED → SAMPLES_REQUIRED →
INVALID_AUDIO → INCONSISTENT_SAMPLES), "Sin consentimiento" y "Con
consentimiento".
"""
import tempfile
import unittest

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import EnrollmentError, SpeakerEnrollment
from speaker_fixtures import EmbedderFalso, F_DUEÑO, F_IMPOSTOR, tono


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


class MuestrasConsistentes(EnrollBase):
    def test_tres_muestras_del_mismo_hablante_crean_la_huella(self):
        muestras = [tono(F_DUEÑO + delta) for delta in (0.0, 2.0, 4.0)]  # misma persona, tomas distintas
        self.assertEqual(self.enrollment.enroll(muestras, consent=True), {"enrolled": True})


class MuestrasDeDosPersonas(EnrollBase):
    def test_min_par_bajo_el_corte_responde_inconsistent_samples(self):
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), tono(F_IMPOSTOR)], consent=True)
        self.assertEqual(captura.exception.code, "INCONSISTENT_SAMPLES")
        self.assertEqual(self.enrollment.status(), {"enrolled": False})  # no queda nada registrado


class VariosErroresALaVez(EnrollBase):
    def test_sin_consentimiento_gana_sobre_todas_las_otras_validaciones(self):
        import numpy as np

        ilegible = np.zeros(16000 * 4, dtype="float32")  # solo silencio
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO), ilegible], consent=False)  # sin consent + 2 muestras + ilegible
        self.assertEqual(captura.exception.code, "CONSENT_REQUIRED")  # el primero del orden
        self.assertEqual(self.embedder.llamadas, 0)  # no se procesó nada (PRIV-2)
        self.assertEqual(self.enrollment.status(), {"enrolled": False})


class SinConsentimiento(EnrollBase):
    def test_consent_false_responde_consent_required_y_no_procesa_nada(self):
        with self.assertRaises(EnrollmentError) as captura:
            self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=False)
        self.assertEqual(captura.exception.code, "CONSENT_REQUIRED")
        self.assertEqual(self.embedder.llamadas, 0)  # ni un embedding
        self.assertEqual(self.enrollment.status(), {"enrolled": False})
        self.assertFalse(self.enrollment.consent_external())


class ConConsentimiento(EnrollBase):
    def test_con_consentimiento_se_procesan_las_muestras(self):
        self.assertEqual(self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True), {"enrolled": True})
        self.assertGreater(self.embedder.llamadas, 0)  # sí se procesaron
        self.assertTrue(self.enrollment.consent_external())


if __name__ == "__main__":
    unittest.main()