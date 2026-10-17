"""Escenarios de privacidad (PRIV-1, PRIV-3, PRIV-4).

"Solo se guardan embeddings", "Nada biométrico en los logs", "Borrado de la
huella" (por script) y "Riesgo documentado" (anti-spoofing fuera de alcance).
"""
import tempfile
import unittest
from pathlib import Path

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import F_DUEÑO, tono


class SoloSeGuardanEmbeddings(unittest.TestCase):
    def test_en_el_directorio_de_datos_no_queda_audio(self):
        temporal = tempfile.TemporaryDirectory()
        try:
            from speaker_fixtures import EmbedderFalso

            verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(temporal.name),
                                       min_verify_seconds=2.0)
            verifier.load()
            SpeakerEnrollment(verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
            verifier.verify(tono(F_DUEÑO), user="usuario")
            archivos = sorted(p.name for p in Path(temporal.name).iterdir())
            permitidos = {"huella.npy", "consent.json", ".gitignore"}
            self.assertTrue(set(archivos).issubset(permitidos), archivos)
            for ruta in Path(temporal.name).iterdir():
                self.assertLess(ruta.stat().st_size, 100_000)  # un embedding son unos cientos de bytes
            self.assertIn("huella.npy", archivos)  # el embedding sí está
        finally:
            temporal.cleanup()


class NadaBiometricoEnLosLogs(unittest.TestCase):
    def test_logs_de_verificacion_y_errores_sin_audio_embeddings_ni_puntajes(self):
        temporal = tempfile.TemporaryDirectory()
        try:
            from speaker_fixtures import EmbedderFalso

            embedder = EmbedderFalso()
            verifier = SpeakerVerifier(embedder=embedder, store=SpeakerStore(temporal.name),
                                       min_verify_seconds=2.0)
            verifier.load()
            SpeakerEnrollment(verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
            embedder.fallo_al_embed = True  # a partir de aquí el modelo falla
            with self.assertLogs("speaker", level="DEBUG") as captura:
                verifier.verify(tono(F_DUEÑO), user="usuario")   # el embed del comando falla
                verifier.verify(tono(700.0), user="usuario")     # también falla
            for registro in captura.records:
                mensaje = registro.getMessage()
                self.assertNotIn("score", mensaje.lower())
                self.assertNotIn("[", mensaje)        # nada de arrays/vectores volcados
                self.assertLess(len(mensaje), 200)    # nada de audio volcado
        finally:
            temporal.cleanup()


class BorradoDeLaHuella(unittest.TestCase):
    def test_borrar_deja_al_usuario_como_no_enrolado_y_retira_el_consentimiento(self):
        temporal = tempfile.TemporaryDirectory()
        try:
            from speaker_fixtures import EmbedderFalso

            store = SpeakerStore(temporal.name)
            verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=store, min_verify_seconds=2.0)
            verifier.load()
            SpeakerEnrollment(verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
            self.assertEqual(verifier.verify(tono(F_DUEÑO), user="usuario")["status"], "VERIFIED")

            import subprocess
            import sys
            from pathlib import Path

            script = Path(__file__).resolve().parents[2] / "scripts" / "delete_voiceprint.py"
            proceso = subprocess.run(
                [sys.executable, str(script), "--data-dir", temporal.name],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proceso.returncode, 0, proceso.stderr)

            self.assertEqual(verifier.verify(tono(F_DUEÑO), user="usuario"),
                             {"status": "NOT_AVAILABLE", "score": None})  # tratado como no enrolado
            self.assertFalse(SpeakerEnrollment(verifier).consent_external())  # consentimiento retirado
            self.assertEqual(SpeakerEnrollment(verifier).status(), {"enrolled": False})
        finally:
            temporal.cleanup()


class RiesgoDocumentado(unittest.TestCase):
    def test_no_hay_anti_spoofing_una_repeticion_vuelve_a_pasar(self):
        """Fuera de alcance en H2 (X-4): la MISMA grabación del usuario vuelve a pasar.
        Contra eso protegen el grant, el "sí" hablado y highAmountThreshold."""
        temporal = tempfile.TemporaryDirectory()
        try:
            from speaker_fixtures import EmbedderFalso

            verifier = SpeakerVerifier(embedder=EmbedderFalso(), store=SpeakerStore(temporal.name),
                                       min_verify_seconds=2.0)
            verifier.load()
            SpeakerEnrollment(verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)
            self.assertEqual(verifier.verify(tono(F_DUEÑO), user="usuario")["status"], "VERIFIED")
            self.assertEqual(verifier.verify(tono(F_DUEÑO), user="usuario")["status"], "VERIFIED")
        finally:
            temporal.cleanup()


if __name__ == "__main__":
    unittest.main()