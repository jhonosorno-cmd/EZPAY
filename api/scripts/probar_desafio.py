r"""Experimento del banco de frases del desafío (solo desarrollo, Windows).

Te muestra una frase del banco; la repites, y el script dice qué entendió Whisper y si cumple el corte del 80 %.
ESPACIO empieza y detiene la grabación; Q sale. Al final muestra un resumen y cuáles frases conviene descartar.
Resultados en ~/ezpay-h3/desafio.csv (sin audio, fuera del repo).

Uso (desde `api/`, en CMD, un comando a la vez):
  set PYTHONPATH=.
  .venv\Scripts\python.exe scripts\probar_desafio.py --quien sebas --ruido silencio
  .venv\Scripts\python.exe scripts\probar_desafio.py --quien sebas --ruido silencio --frases 1-10
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.desafio import agregar_fila, evaluar, ruta_por_defecto, seleccionar  # noqa: E402
from scripts.grabar_y_transcribir import _cargar_env, _esperar_espacio, _grabar_hasta_espacio  # noqa: E402
from voice.challenge import load_bank  # noqa: E402
from voice.config import CHALLENGE_MIN_MATCH  # noqa: E402
from voice.engines import _pcm_to_wav_bytes, build_default_engines  # noqa: E402
from voice.transcribe import TranscribeInputError, transcribe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba las frases del desafío con tu voz (sin guardar audio).")
    parser.add_argument("--quien", default="", help="quién habla")
    parser.add_argument("--ruido", default="", help="condición: silencio, tele, lejos...")
    parser.add_argument("--frases", default="", help="cuáles frases del banco, por número: 1,3,5-7 (por defecto todas)")
    parser.add_argument("--csv", default="", help="ruta del CSV (por defecto ~/ezpay-h3/desafio.csv)")
    args = parser.parse_args()
    _cargar_env()
    banco = load_bank()
    try:
        elegidas = seleccionar(args.frases, banco)
    except ValueError as err:
        parser.error(str(err))
    ruta = Path(args.csv) if args.csv else ruta_por_defecto()
    engines = build_default_engines()
    print(f"Banco: {len(banco)} frases. Corte de coincidencia: {CHALLENGE_MIN_MATCH:.0%}. Resultados en: {ruta}")
    print("ESPACIO = empezar/detener, Q = salir.\n")

    resultados = []
    for orden, (numero, frase) in enumerate(elegidas, 1):
        print(f"[{orden}/{len(elegidas)}] (frase {numero}) REPITE: \"{frase}\"")
        print("  Pulsa ESPACIO para empezar a grabar (Q para salir)...", flush=True)
        if _esperar_espacio() == "q":
            break
        pcm = _grabar_hasta_espacio()
        try:
            t = transcribe(_pcm_to_wav_bytes(pcm), "desafio-test", consent_external=True, engines=engines)
        except TranscribeInputError as err:
            print(f"  Error de audio: {err.code.value} - {err}\n")
            continue
        r = evaluar(frase, t.text, t.had_speech)
        agregar_fila(ruta, quien=args.quien, ruido=args.ruido, numero=numero, frase=frase, texto=t.text,
                     motor=t.engine.value, hubo_voz=t.had_speech, resultado=r)
        resultados.append((numero, frase, r))
        print(f"  ENTENDIÓ: \"{t.text.strip()}\"   (motor: {t.engine.value})")
        print(f"  COINCIDENCIA: {r.puntaje:.0%} -> {r.veredicto}\n")

    if resultados:
        ok = sum(1 for _, _, r in resultados if r.veredicto == "CUMPLE")
        print(f"--- Resumen: {ok} de {len(resultados)} cumplen el {CHALLENGE_MIN_MATCH:.0%} ---")
        for numero, frase, r in resultados:
            if r.veredicto != "CUMPLE":
                print(f"  Descartar o revisar la {numero}: \"{frase}\" ({r.puntaje:.0%}, {r.veredicto})")
    print("Fin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
