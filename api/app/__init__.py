"""Backend FastAPI de EZPAY: rutas del Contrato B y orquestador del turno (turn-orchestration).

Une los motores que ya existen en `api/`: voz (ML 1), motor de decisión, PIN y verificación de
hablante (ML 2) y el cliente de Node (Pagos). Arranque, desde `api/`:
`uvicorn app.main:app --port 8000`.
"""
