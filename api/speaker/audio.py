"""Audio de entrada del hablante: recorte de silencios fijado por calibración.

`trim_silence` es EXACTAMENTE la función con que se calibró el umbral 0.45
(experimentos ML 2, 15 oct): ventanas de 320 muestras (20 ms a 16 kHz), umbral
0,1 × RMS máximo y 0,25 s de margen a cada lado. Cambiar la función o sus
parámetros obliga a recalibrar el umbral de verificación y el corte de
consistencia (spec `speaker-verification`).
"""
import numpy as np

SAMPLE_RATE = 16000  # PCM float32 mono 16 kHz (lo decodifica Voz, contrato-voz §4)


def trim_silence(audio, frame=320, pad=0.25):
    """Quita el silencio del principio y del final (detector de energía muy simple)."""
    if len(audio) < frame:
        return audio
    n = len(audio) // frame
    rms = np.sqrt((audio[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
    voiced = np.nonzero(rms > 0.1 * rms.max())[0]
    if len(voiced) == 0:
        return audio
    p = int(pad * SAMPLE_RATE)
    return audio[max(0, voiced[0] * frame - p): min(len(audio), (voiced[-1] + 1) * frame + p)]


def duracion_voz_util(pcm):
    """Segundos de voz útil: EXACTAMENTE la medida de la calibración del 16–17 oct.

    Es `len(trim_silence(pcm, frame=320, pad=0.25)) / SAMPLE_RATE`, que incluye
    el margen de 0,25 s de cada lado (así se cortaron los truncados de X-2 y así
    se calibraron 2,0 s / 3 s / 15 s). Con audio sin voz detectable devuelve 0.
    Cambiar esta medida obliga a recalibrar umbral y corte de consistencia.
    """
    pcm = np.asarray(pcm, dtype="float32")
    if pcm.size == 0:
        return 0.0
    if pcm.size < 320:  # más corto que una ventana: trim lo deja pasar tal cual
        return pcm.size / SAMPLE_RATE
    n = pcm.size // 320
    rms = np.sqrt((pcm[: n * 320].reshape(n, 320) ** 2).mean(axis=1))
    voiced = np.nonzero(rms > 0.1 * rms.max())[0] if float(rms.max()) > 0.0 else np.array([], dtype=int)
    if len(voiced) == 0:
        return 0.0  # sin voz: no hay frase que medir
    return trim_silence(pcm).size / SAMPLE_RATE