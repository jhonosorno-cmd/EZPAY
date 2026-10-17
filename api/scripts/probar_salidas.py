r"""Prueba de punta a punta de TU parte (solo desarrollo, Windows): graba un comando y muestra el JSON que
recibirían Pagos, Frontend y ML 2. Después puedes grabar la respuesta ("sí" o "no") a la confirmación.

ESPACIO empieza y detiene la grabación; Q sale. Valores simulados: cotización sin costo, voz no disponible,
presupuesto concedido y la agenda provisional. Nada se guarda en disco.

Uso (desde `api/`, en CMD):
  set PYTHONPATH=.
  .venv\Scripts\python.exe scripts\probar_salidas.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decision.context_io import decide_dict  # noqa: E402
from scripts.grabar_y_transcribir import _cargar_env, _esperar_espacio, _grabar_hasta_espacio  # noqa: E402
from scripts.salidas import salidas_de_la_respuesta, salidas_del_comando  # noqa: E402
from voice.engines import _pcm_to_wav_bytes, build_default_engines  # noqa: E402
from voice.transcribe import TranscribeInputError, transcribe  # noqa: E402


def _imprimir(titulo: str, datos) -> None:
    print(f"\n--- {titulo} ---")
    print(json.dumps(datos, ensure_ascii=False, indent=2))


def _grabar_y_transcribir(engines):
    print("  Pulsa ESPACIO para empezar a grabar (Q para salir)...", flush=True)
    if _esperar_espacio() == "q":
        return None
    pcm = _grabar_hasta_espacio()
    return transcribe(_pcm_to_wav_bytes(pcm), "salidas-test", consent_external=True, engines=engines)


def main() -> int:
    _cargar_env()
    engines = build_default_engines()
    print('Di un comando, por ejemplo: "Envíale veinte mil a Laura hija".')
    try:
        t = _grabar_y_transcribir(engines)
    except TranscribeInputError as err:
        print(f"Error de audio: {err.code.value} - {err}")
        return 1
    if t is None:
        return 0
    salidas = salidas_del_comando(t.text, t.had_speech, t.engine.value)
    _imprimir("1. Para Frontend: transcripción (Contrato B)", salidas["transcript"])
    _imprimir("2. Para ML 2: intención", salidas["intent"])
    _imprimir("3. Para ML 2: destinatario resuelto", salidas["resolution"])
    _imprimir("4. Para ML 2: context completo (con valores simulados)", salidas["context"])
    _imprimir("5. Decisión del motor de ML 2", salidas["decision"])
    print(f"\n--- 6. Lo que se le dice a la persona (say) ---\n{salidas['say']}")
    if salidas["decision"]["decision"] != "ASK_PIN":
        return 0
    print('\nEl motor pide PIN. Para seguir, suponemos PIN correcto y que ahora pide confirmar.')
    print('Di "sí" o "no" a la confirmación.')
    ctx = dict(salidas["context"], phase="PIN", pin={"result": "OK", "sessionFailures": 0, "locked": False})
    print(f'Motor tras el PIN: {decide_dict(ctx)}')
    try:
        r = _grabar_y_transcribir(engines)
    except TranscribeInputError as err:
        print(f"Error de audio: {err.code.value} - {err}")
        return 1
    if r is None:
        return 0
    final = salidas_de_la_respuesta(salidas["context"], r.text)
    _imprimir(f'7. Respuesta "{r.text.strip()}" -> decisión', {"reply": final["reply"], **final["decision"]})
    print(f"\n--- 8. Mensaje final (say) ---\n{final['say'] or '(pago confirmado: el mensaje lo da COMPLETED después del pago)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
