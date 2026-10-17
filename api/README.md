# api

Backend Python (FastAPI): esqueleto y cliente de Node (Pagos), voz (Voz), motor, verificación de hablante y PIN (Verificación y calidad).
Specs: `add-payments-client`, `add-voice-understanding`. Contratos: A (cliente) y B (servidor).

Variables de entorno: `NODE_BASE_URL` (por defecto `http://localhost:4000/v1`), `ASSET_CODE`/`ASSET_SCALE` (demo: `COP`/`2`),
`EZPAY_WALLET_ADDRESS` (wallet emisora del grant) y `EZPAY_PIN_HASH` (ver `pin/README.md` y `.env.example` de ML 2).

Esqueleto Contrato B (Pagos): desde `api/`, arrancá con `uvicorn app.main:app --port 8000` (con el venv: `.venv\Scripts\python -m uvicorn app.main:app --port 8000`) y corré sus pruebas con `PYTHONPATH=. .venv\Scripts\python -m unittest discover -s tests/app`.
