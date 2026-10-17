"""Escenarios de voice-enrollment: huella, ciclo de vida y consulta de estado.

"Consentimiento único (huella + proveedor externo)", "Re-enrolamiento
sobrescribe", "Re-enrolamiento fallido conserva la huella", "Huella como
promedio", "Reinicio del backend conserva la huella", "Consulta de estado" y
"Sin datos biométricos en los logs" (lado del enrolamiento).
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


class ConsentimientoUnico(EnrollBase):
    def test_enrolar_registra_consent_externo_y_borrar_lo_retira(self):
        self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        self.assertTrue(self.enrollment.consent_external())  # Voz consulta consentExterno == true
        self.enrollment.delete()
        self.assertFalse(self.enrollment.consent_external())  # vuelve a false (PRIV-3)


class ReEnrolamientoSobrescribe(EnrollBase):
    def test_un_nuevo_enrolamiento_valido_reemplaza_la_huella(self):
        self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        resultado = self.enrollment.enroll([tono(F_DUEÑO + 2.0)] * 3, consent=True)
        self.assertEqual(resultado, {"enrolled": True})  # 201 del route
        verifier = self.enrollment.verifier
        self.assertEqual(verifier.verify(tono(F_DUEÑO + 2.0), user="usuario")["status"], "VERIFIED")


class ReEnrolamientoFallidoConservaLaHuella(EnrollBase):
    def test_un_intent_invalido_no_borra_la_huella_anterior(self):
        self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        with self.assertRaises(EnrollmentError) as captura:
            # re-enrolamiento con muestras de DOS personas: inconsistentes (B-4)
            self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), tono(F_IMPOSTOR)], consent=True)
        self.assertEqual(captura.exception.code, "INCONSISTENT_SAMPLES")
        # la huella anterior sigue viva y funcional
        verifier = self.enrollment.verifier
        self.assertEqual(verifier.verify(tono(F_DUEÑO), user="usuario")["status"], "VERIFIED")
        self.assertEqual(self.enrollment.status(), {"enrolled": True})


class HuellaComoPromedio(EnrollBase):
    def test_la_huella_guardada_es_el_promedio_l2_de_los_3_embeddings(self):
        muestras = [tono(F_DUEÑO + d) for d in (0.0, 2.0, 4.0)]
        self.enrollment.enroll(muestras, consent=True)
        import numpy as np

        embs = [self.enrollment.verifier.embed(m) for m in muestras]  # los mismos embeddings que usó enroll
        esperado = np.mean(np.stack(embs), axis=0)
        esperado = esperado / np.linalg.norm(esperado)
        guardado = self.enrollment.verifier.store.load(usuario="usuario")
        self.assertTrue(np.allclose(np.asarray(guardado), esperado, atol=1e-6))
        self.assertAlmostEqual(float(np.linalg.norm(np.asarray(guardado))), 1.0, places=5)  # L2-normalizada


class ReinicioDelBackendConservaLaHuella(EnrollBase):
    def test_un_nuevo_verifier_carga_la_huella_del_archivo(self):
        self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        # "reinicio": instancias nuevas sobre el MISMO directorio de datos
        otro_verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)
        otro_verifier.load()
        otro_enrollment = SpeakerEnrollment(otro_verifier)
        self.assertEqual(otro_enrollment.status(), {"enrolled": True})
        self.assertEqual(otro_verifier.verify(tono(F_DUEÑO), user="usuario")["status"], "VERIFIED")
        self.assertTrue(otro_enrollment.consent_external())  # el consentimiento también persiste


class ConsultaDeEstado(EnrollBase):
    def test_status_responde_solo_enrolled_y_nada_biometrico(self):
        self.assertEqual(self.enrollment.status(), {"enrolled": False})
        self.enrollment.enroll([tono(F_DUEÑO)] * 3, consent=True)
        self.assertEqual(self.enrollment.status(), {"enrolled": True})


class SinDatosBiometricosEnLosLogs(EnrollBase):
    def test_logs_de_enrolamiento_y_errores_sin_audio_embeddings_ni_puntajes(self):
        import numpy as np

        with self.assertLogs("speaker", level="DEBUG") as captura:
            try:
                self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), np.zeros(0, "float32")], consent=True)
            except EnrollmentError:
                pass  # INVALID_AUDIO también queda en el log, sin datos
            try:
                self.enrollment.enroll([tono(F_DUEÑO), tono(F_DUEÑO), tono(F_IMPOSTOR)], consent=True)
            except EnrollmentError:
                pass  # INCONSISTENT_SAMPLES, sin puntajes
        for registro in captura.records:
            mensaje = registro.getMessage()
            self.assertNotIn("[", mensaje)      # nada de arrays
            self.assertNotIn("score", mensaje.lower())
            self.assertLess(len(mensaje), 200)  # nada de audio volcado


if __name__ == "__main__":
    unittest.main()