# api

Backend Python (FastAPI): esqueleto y cliente de Node (Pagos), voz (Voz), motor, verificación de hablante y PIN (Verificación y calidad).
Specs: `add-payments-client`, `add-voice-understanding`. Contratos: A (cliente) y B (servidor).

Esqueleto Contrato B (Pagos): desde `api/`, arrancá con `uvicorn app.main:app --port 8000` (con el venv: `.venv\Scripts\python -m uvicorn app.main:app --port 8000`) y corré sus pruebas con `PYTHONPATH=. .venv\Scripts\python -m unittest discover -s tests/app`.
