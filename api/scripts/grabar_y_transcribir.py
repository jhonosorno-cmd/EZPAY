"""Prueba manual y en vivo de speech-transcription desde la terminal (solo desarrollo, Windows).

Te va mostrando qué decir. ESPACIO empieza a grabar, ESPACIO detiene y transcribe, Q sale.
Graba en memoria (nunca en disco) y pasa el audio por TODO el pipeline de `transcribe`
(cabecera, filtro de no-habla, Groq solo con consentimiento y respaldo local). El audio se descarta.

Requiere `pip install sounddevice` (solo para esta prueba; no está en requirements.txt).

Uso (desde `api/`, en CMD):
  set PYTHONPATH=.
  .venv\\Scripts\\python.exe scripts\\grabar_y_transcribir.py                 # con consentimiento: Groq si hay GROQ_API_KEY
  .venv\\Scripts\\python.exe scripts\\grabar_y_transcribir.py --sin-consent   # fuerza la vía local
  .venv\\Scripts\\python.exe scripts\\grabar_y_transcribir.py --quien ana --ruido tele   # batería de H3: añade filas
  (sin audio) al CSV ~/ezpay-h3/resultados.csv, fuera del repo; --csv cambia la ruta
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

from scripts.bateria import agregar_fila, evaluar, ruta_por_defecto, seleccionar_frases  # noqa: E402
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
    # Sin normalizar: el navegador tampoco lo hace, y subir el volumen amplifica el ruido de fondo.
    return pcm


def main() -> int:
    parser = argparse.ArgumentParser(description="Graba y transcribe en vivo (sin guardar audio).")
    parser.add_argument("--ruido", default="", help="condición de la tanda: silencio, tele, lejos...")
    parser.add_argument("--frases", default="", help="cuáles frases pedir, por número: 1,3,5-7 (por defecto todas)")
    parser.add_argument("--quien", default="", help="quién habla (para el CSV)")
    parser.add_argument("--csv", default="", help="ruta del CSV de resultados (por defecto ~/ezpay-h3/resultados.csv)")
    parser.add_argument("--sin-consent", action="store_true", help="fuerza el motor local (sin Groq)")
    args = parser.parse_args()
    _cargar_env()
    print("GROQ_API_KEY:", "definida" if os.environ.get("GROQ_API_KEY") else "NO definida (se usará el motor local)")
    try:
        frases = seleccionar_frases(args.frases)
    except ValueError as err:
        parser.error(str(err))
    engines = build_default_engines()
    ruta = Path(args.csv) if args.csv else ruta_por_defecto()
    print(f"Resultados (sin audio) en: {ruta}")
    print(f"Modo: {'LOCAL (sin consentimiento)' if args.sin_consent else 'con consentimiento (Groq si hay GROQ_API_KEY, si no local)'}")
    print("ESPACIO = empezar/detener, Q = salir.\n")

    for orden, (i, frase) in enumerate(frases, 1):
        print(f"[{orden}/{len(frases)}] DI: \"{frase.decir}\"")
        print("  Pulsa ESPACIO para empezar a grabar (Q para salir)...", flush=True)
        if _esperar_espacio() == "q":
            break
        pcm = _grabar_hasta_espacio()
        try:
            r = transcribe(_pcm_to_wav_bytes(pcm), "terminal-test",
                           consent_external=not args.sin_consent, engines=engines)
            print(f"  TEXTO : \"{r.text}\"   (motor: {r.engine.value}, hubo voz: {r.had_speech})")
            resultado = evaluar(frase, r.text, r.had_speech)
            agregar_fila(ruta, quien=args.quien, ruido=args.ruido, numero=i, frase=frase, texto=r.text,
                         motor=r.engine.value, hubo_voz=r.had_speech, resultado=resultado)
            print(f"  VEREDICTO: {resultado.veredicto}   (el sistema entendió: {resultado.interpretado})")
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
