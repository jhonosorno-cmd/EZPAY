# api

Backend Python (FastAPI): esqueleto y cliente de Node (Pagos), voz (Voz), motor, verificación de hablante y PIN (Verificación y calidad).
Specs: `add-payments-client`, `add-voice-understanding`. Contratos: A (cliente) y B (servidor).

## Correr el backend (Contrato B en el puerto 8000)

Desde `api/`, con Python 3.12:

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env        # completar EZPAY_PIN_HASH, EZPAY_WALLET_ADDRESS, EZPAY_AGENDA_PATH...
.venv/bin/uvicorn app.main:app --port 8000
```

`app/` carga `api/.env` sin pisar el entorno. Necesita Node en `NODE_BASE_URL` (servicio real de
`payments/` o el mock `npm run mock:a` en la raíz). El frontend (`web/`, `npm run dev`) llega por el
proxy de Vite a `/api`. Al arrancar, el log dice si el modelo de hablante y la wallet están listos:
sin modelo, toda verificación da `NOT_AVAILABLE` y el motor pide PIN; sin `av`/`faster-whisper`,
solo funcionan los turnos por texto.

Pruebas (toda la suite de `api/`):

```bash
PYTHONPATH=.:tests/app .venv/bin/python -m pytest tests -q
```

| Archivo | Qué hace |
|---|---|
| `app/main.py` | Rutas del Contrato B, CORS (solo el origen del frontend), logs sin cuerpo del request |
| `app/orchestrator.py` | Turno: intención → agenda → voz → quote → motor → `TurnState` y llamadas a Node |
| `app/state.py` | Sesiones en memoria; grant de presupuesto e historial en `api/.data/app/` (fuera de git) |
| `app/voice_io.py` | Transcripción y verificación sobre el mismo PCM; enrolamiento |

En Windows el venv queda en `.venv\Scripts\python`.
