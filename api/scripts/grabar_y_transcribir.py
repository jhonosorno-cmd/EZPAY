"""Prueba manual y en vivo de speech-transcription desde la terminal (solo desarrollo, Windows).

Te va mostrando qué decir. ESPACIO empieza a grabar, ESPACIO detiene y transcribe, Q sale.
Graba en memoria (nunca en disco) y pasa el audio por TODO el pipeline de `transcribe`
(cabecera, filtro de no-habla, Groq solo con consentimiento y respaldo local). El audio se descarta.

Requiere `pip install sounddevice` (solo para esta prueba; no está en requirements.txt).

Uso (desde `api/`, en CMD):
  set PYTHONPATH=.
  .venv\\Scripts\\python.exe scripts\\grabar_y_transcribir.py                 # con consentimiento: Groq si hay GROQ_API_KEY
  .venv\\Scripts\\python.exe scripts\\grabar_y_transcribir.py --sin-consent   # fuerza la vía local
"""
import argparse
import msvcrt
import os
import sys
import time
from pathlib import Path

import av
import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice.config import SAMPLE_RATE  # noqa: E402
from voice.engines import _pcm_to_wav_bytes, build_default_engines  # noqa: E402
from voice.transcribe import TranscribeInputError, transcribe  # noqa: E402

def _cargar_env() -> None:
    """Carga `api/.env` o el `.env` de la raíz (ignorados por git) sin pisar variables ya definidas."""
    raiz = Path(__file__).resolve().parents[1]
    for ruta in (raiz / ".env", raiz.parent / ".env"):
        if not ruta.is_file():
            continue
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                nombre, valor = linea.split("=", 1)
                os.environ.setdefault(nombre.strip(), valor.strip().strip('"').strip("'"))


MAX_SEGUNDOS = 15  # igual que el tope del navegador

# (qué decir, qué se espera que salga)
FRASES = [
    ("Envíale veinte mil a Laura hija", "orden de pago"),
    ("Mándale cincuenta mil pesos a mi mamá", "orden de pago"),
    ("Paga ciento cincuenta mil a Laura hija", "orden de pago"),
    ("Sí", "afirmativo"),
    ("No", "negativo"),
    ("Confirmo", "afirmativo"),
    ("Cancela", "negativo"),
    ("Mmm... no sé", "respuesta poco clara"),
    ("(silencio, no digas nada)", "texto vacío y hadSpeech False"),
    ("Dilo con ruido: pon música o habla una tele y di 'envíale veinte mil a Laura hija'", "orden de pago con ruido"),
]


def _esperar_espacio() -> str:
    """Bloquea hasta ESPACIO ('espacio') o Q ('q')."""
    while True:
        tecla = msvcrt.getwch().lower()
        if tecla == " ":
            return "espacio"
        if tecla == "q":
            return "q"


def _grabar_hasta_espacio() -> np.ndarray:
    """Graba del micrófono por defecto hasta otro ESPACIO; entrega PCM float32 16 kHz mono en memoria."""
    dispositivo = sd.query_devices(kind="input")
    rate_in = int(dispositivo["default_samplerate"])
    trozos: list[np.ndarray] = []

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        trozos.append(indata.copy())

    inicio = time.monotonic()
    with sd.InputStream(samplerate=rate_in, channels=1, dtype="float32", callback=callback):
        print("  >>> GRABANDO... habla y pulsa ESPACIO para detener", flush=True)
        while time.monotonic() - inicio < MAX_SEGUNDOS:
            if msvcrt.kbhit() and msvcrt.getwch() == " ":
                break
            time.sleep(0.02)
    if not trozos:
        return np.zeros(0, dtype="float32")
    grabado = np.concatenate(trozos)  # (n, 1)
    print(f"  Listo ({time.monotonic() - inicio:.1f} s).")
    resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
    frame = av.AudioFrame.from_ndarray(grabado.T, format="fltp", layout="mono")
    frame.sample_rate = rate_in
    partes = [f.to_ndarray().reshape(-1) for f in resampler.resample(frame)]
    pcm = np.concatenate(partes).astype("float32")
    pico = float(np.max(np.abs(pcm))) if pcm.size else 0.0
    if pico >= 0.05:  # solo normaliza si hubo señal real; el silencio se queda callado (filtro)
        pcm /= pico
    return pcm


def main() -> int:
    parser = argparse.ArgumentParser(description="Graba y transcribe en vivo (sin guardar audio).")
    parser.add_argument("--sin-consent", action="store_true", help="fuerza el motor local (sin Groq)")
    args = parser.parse_args()
    _cargar_env()
    print("GROQ_API_KEY:", "definida" if os.environ.get("GROQ_API_KEY") else "NO definida (se usará el motor local)")
    engines = build_default_engines()
    print(f"Modo: {'LOCAL (sin consentimiento)' if args.sin_consent else 'con consentimiento (Groq si hay GROQ_API_KEY, si no local)'}")
    print("ESPACIO = empezar/detener, Q = salir.\n")

    for i, (decir, esperado) in enumerate(FRASES, 1):
        print(f"[{i}/{len(FRASES)}] DI: \"{decir}\"")
        print(f"       Esperado: {esperado}")
        print("  Pulsa ESPACIO para empezar a grabar (Q para salir)...", flush=True)
        if _esperar_espacio() == "q":
            break
        pcm = _grabar_hasta_espacio()
        try:
            r = transcribe(_pcm_to_wav_bytes(pcm), "terminal-test",
                           consent_external=not args.sin_consent, engines=engines)
            print(f"  TEXTO : \"{r.text}\"   (motor: {r.engine.value}, hubo voz: {r.had_speech})")
            if r.engine.value == "local" and not args.sin_consent:
                try:  # diagnóstico: por qué Groq no respondió (los errores del proveedor no incluyen la llave)
                    engines.remote.transcribe(pcm)
                except Exception as err:  # noqa: BLE001
                    print(f"  (Groq no respondió: {type(err).__name__}: {err})")
            print()
        except TranscribeInputError as err:
            print(f"  Error de audio: {err.code.value} - {err}\n")
    print("Fin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
