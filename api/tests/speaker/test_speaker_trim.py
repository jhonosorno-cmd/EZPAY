"""Escenarios del recorte de silencios fijado (speaker-verification).

"Mismo recorte en enrolamiento y verificación": `speaker.audio.trim_silence`
es EXACTAMENTE la función de calibración (ventanas de 320 muestras = 20 ms a
16 kHz, margen de 0,25 s, umbral 0,1 × RMS máximo). "Cambiar el recorte exige
recalibrar": la prueba fija los parámetros calibrados.
"""
import inspect
import unittest

import numpy as np

from speaker import SAMPLE_RATE, duracion_voz_util, trim_silence
from speaker_fixtures import F_DUEÑO, tono


def trim_silence_calibrado(audio, frame=320, pad=0.25):
    """COPIA de la función de calibración ML 2 (Pruebas ML2/voice_demo.py, 15 oct)."""
    if len(audio) < frame:
        return audio
    n = len(audio) // frame
    rms = np.sqrt((audio[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    voiced = np.nonzero(rms > 0.1 * rms.max())[0]
    if len(voiced) == 0:
        return audio
    p = int(pad * SAMPLE_RATE)
    return audio[max(0, voiced[0] * frame - p): min(len(audio), (voiced[-1] + 1) * frame + p)]


class MismoRecorteEnEnrolamientoYVerificacion(unittest.TestCase):
    def test_los_defaults_son_los_calibrados(self):
        firma = inspect.signature(trim_silence)
        self.assertEqual(firma.parameters["frame"].default, 320)
        self.assertEqual(firma.parameters["pad"].default, 0.25)

    def test_trim_silence_coincide_con_la_funcion_de_calibracion(self):
        casos = [
            tono(150.0, segundos=4.0, silencio_inicial=0.5, silencio_final=0.5),
            tono(700.0, segundos=2.0, silencio_inicial=0.1, silencio_final=0.3),
            np.concatenate([tono(150.0), tono(400.0)]),
            tono(150.0, segundos=31.0, silencio_inicial=0.0, silencio_final=0.0),
            np.zeros(1600, dtype="float32"),          # todo silencio
            np.zeros(100, dtype="float32"),            # más corto que una ventana
            tono(150.0, segundos=0.05, silencio_inicial=0.0, silencio_final=0.0),
        ]
        for audio in casos:
            self.assertEqual(trim_silence(audio).tolist(), trim_silence_calibrado(audio).tolist(),
                             f"diverge en un audio de {audio.size} muestras")

    def test_enrolamiento_y_verificacion_recortan_igual(self):
        audio = tono(150.0, segundos=4.0, silencio_inicial=0.7, silencio_final=0.9)
        # el mismo PCM entra a los dos caminos: la voz útil es idéntica (una sola función)
        self.assertEqual(trim_silence(audio).size, trim_silence(trim_silence(audio)).size)


class CambiarElRecorteExigeRecalibrar(unittest.TestCase):
    def test_el_par_calibrado_recorte_umbral_esta_fijado(self):
        firma = inspect.signature(trim_silence)
        self.assertEqual((firma.parameters["frame"].default, firma.parameters["pad"].default), (320, 0.25))
        from speaker import verification

        self.assertEqual(verification.UMBRAL_DEFECTO, 0.45)
        self.assertEqual(verification.MIN_VERIFY_SECONDS_DEFECTO, 2.0)
        self.assertEqual(verification.MAX_SEGUNDOS, 30.0)


class LaMedidaEsLaDeLaCalibracion(unittest.TestCase):
    """No-regresión de la desviación 1: voz útil se mide COMO la calibración del
    16–17 oct, len(trim_silence(x))/16000, CON el margen de 0,25 s de cada lado.
    Medir sin margen deja tomas genuinas de ~2 s en NOT_AVAILABLE (PIN en demo)."""

    def test_coincide_con_len_trim_silence_para_varios_audios(self):
        casos_con_voz = [
            tono(F_DUEÑO, segundos=4.0, silencio_inicial=0.5, silencio_final=0.5),
            tono(700.0, segundos=2.1, silencio_inicial=0.25, silencio_final=0.25),
            tono(150.0, segundos=1.9, silencio_inicial=0.3, silencio_final=0.4),
            np.concatenate([tono(150.0), tono(400.0)]),
            tono(150.0, segundos=0.05, silencio_inicial=0.0, silencio_final=0.0),
        ]
        for audio in casos_con_voz:
            self.assertAlmostEqual(duracion_voz_util(audio), len(trim_silence(audio)) / SAMPLE_RATE,
                                   delta=1e-9, msg=f"diverge en audio de {audio.size} muestras")

    def test_con_audio_sin_voz_la_medida_es_cero(self):
        self.assertEqual(duracion_voz_util(np.zeros(16000 * 4, dtype="float32")), 0.0)
        self.assertEqual(duracion_voz_util(np.zeros(0, dtype="float32")), 0.0)

    def test_el_margen_de_0_25_s_cuenta_en_la_medida(self):
        # 1,6 s de voz con ≥ 0,25 s de silencio a cada lado ⇒ 1,6 + 0,5 = 2,1 s
        self.assertAlmostEqual(duracion_voz_util(tono(F_DUEÑO, segundos=2.1, silencio_inicial=0.25, silencio_final=0.25)),
                               2.1, delta=1e-9)
        # 1,4 s de voz ⇒ 1,9 s
        self.assertAlmostEqual(duracion_voz_util(tono(F_DUEÑO, segundos=1.9, silencio_inicial=0.25, silencio_final=0.25)),
                               1.9, delta=1e-9)


if __name__ == "__main__":
    unittest.main()