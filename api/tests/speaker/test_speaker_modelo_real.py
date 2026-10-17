"""Escenarios de integración con el modelo REAL (ECAPA): latencia y carga sin red.

Corren SOLO si EZPAY_SPEAKER_MODEL_DIR apunta a los pesos locales
(pretrained_models/spkrec-ecapa-voxceleb); si no, se saltan (skipTest).
"""
import os
import tempfile
import time
import unittest

from speaker import SpeakerStore, SpeakerVerifier
from speaker.enrollment import SpeakerEnrollment
from speaker_fixtures import tono

DIR_MODELO = os.environ.get("EZPAY_SPEAKER_MODEL_DIR", "")


@unittest.skipUnless(DIR_MODELO, "EZPAY_SPEAKER_MODEL_DIR no está definida: sin modelo real")
class ModeloRealBase(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.verifier = SpeakerVerifier(store=SpeakerStore(self.temporal.name),
                                        min_verify_seconds=2.0)  # sin embedder inyectado: el real
        self.verifier.load()
        self.assertFalse(self.verifier.error_de_carga)  # el modelo real cargó

    def tearDown(self):
        self.temporal.cleanup()


class PresupuestoDeLatencia(ModeloRealBase):
    def test_un_comando_de_hasta_10_segundos_verifica_en_menos_de_1_segundo(self):
        comando = tono(150.0, segundos=10.0, silencio_inicial=0.5, silencio_final=0.5)
        huella = self.verifier.embed(comando)  # hace de "usuario enrolado"
        self.verifier.store.save(huella, usuario="usuario", consent_externo=True)
        inicio = time.perf_counter()
        resultado = self.verifier.verify(comando, user="usuario")
        transcurrido = time.perf_counter() - inicio
        self.assertLess(transcurrido, 1.0, "la verificación de ≤ 10 s debe responder en < 1 s")
        self.assertEqual(resultado["status"], "VERIFIED")  # mismo audio: coseno 1.0
        self.assertAlmostEqual(resultado["score"], 1.0, delta=1e-5)


class CargaSinInternet(ModeloRealBase):
    def test_el_modelo_carga_desde_la_cache_local_con_hf_hub_offline(self):
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")  # el embedder lo fuerza antes de importar
        resultado = self.verifier.verify(tono(150.0), user="nadie")
        self.assertEqual(resultado, {"status": "NOT_AVAILABLE", "score": None})  # sin huella: falla cerrada


if __name__ == "__main__":
    unittest.main()