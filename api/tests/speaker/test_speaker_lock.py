"""Scenario "Dos peticiones simultáneas": el candado serializa el acceso al modelo.

Una verificación a la vez; las peticiones en paralelo esperan su turno.
"""
import tempfile
import threading
import time
import unittest

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import EmbedderFalso, F_DUEÑO, tono


class DosPeticionesSimultaneas(unittest.TestCase):
    def test_dos_hilos_se_serializan_y_ambas_responden(self):
        temporal = tempfile.TemporaryDirectory()
        try:
            embedder = EmbedderFalso(latencia=0.15)
            verifier = SpeakerVerifier(embedder=embedder, store=SpeakerStore(temporal.name),
                                       min_verify_seconds=2.0)
            verifier.load()
            SpeakerEnrollment(verifier).enroll([tono(F_DUEÑO)] * 3, consent=True)

            resultados = []

            def verificar():
                resultados.append(verifier.verify(tono(F_DUEÑO), user="usuario"))

            inicio = time.perf_counter()
            hilos = [threading.Thread(target=verificar) for _ in range(2)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join()
            transcurrido = time.perf_counter() - inicio

            self.assertEqual(len(resultados), 2)
            self.assertTrue(all(r["status"] == "VERIFIED" for r in resultados))
            self.assertEqual(embedder.max_concurrencia, 1)  # una a la vez
            self.assertGreaterEqual(transcurrido, 0.3)  # serializadas: ~2 × latencia
        finally:
            temporal.cleanup()


if __name__ == "__main__":
    unittest.main()