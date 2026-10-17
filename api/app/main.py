"""Esqueleto FastAPI del Contrato B (rutas, sesiones, estados). Sin orquestador, sin Node.

Los logs por request llevan SOLO requestId, método, ruta, status, duración y (en /api/turns)
el estado del turno: nunca el cuerpo del request, ni el PIN, ni audio, ni transcripciones.
"""
import json
import logging
import re
import time
import uuid

from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import CORS_ORIGIN, LOG_NAME, PLACEHOLDER_INTERACT_URL, asset_code, asset_scale
from .orchestrator import Deps, default_deps, handle_turn
from .sessions import Session, SessionNotFound, SessionStore
from .states import TurnState
from . import turns as turn_logic

_DIGITS_ONLY = re.compile(r"^\d+$")


class LogFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()


def _get_logger():
    logger = logging.getLogger(LOG_NAME)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(LogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _valid_amount(raw) -> bool:
    """CONV-1: {value: string de solo dígitos, assetCode: str, assetScale: entero ≥ 0}."""
    if not isinstance(raw, dict):
        return False
    value, code, scale = raw.get("value"), raw.get("assetCode"), raw.get("assetScale")
    return (
        isinstance(value, str)
        and _DIGITS_ONLY.fullmatch(value) is not None
        and isinstance(code, str)
        and bool(code)
        and isinstance(scale, int)
        and not isinstance(scale, bool)
        and scale >= 0
    )


def _zero_amount(like: dict) -> dict:
    return {"value": "0", "assetCode": like.get("assetCode", asset_code()), "assetScale": like.get("assetScale", asset_scale())}


def create_app(
    *,
    transcriber=None,
    verifier=None,
    clock=None,
    payments=None,
    agenda_path=None,
    pin_validator=None,
) -> FastAPI:
    """Crea la app. Los puertos y el cliente de Node son inyectables (las pruebas
    usan dobles); sin adaptador el servidor arranca igual y degrada según el spec."""
    app = FastAPI(title="EZPAY api (esqueleto Contrato B)", docs_url=None, redoc_url=None)
    logger = _get_logger()
    store = SessionStore()
    budget: dict = {}
    enrolled = {"value": False}
    deps: Deps = default_deps(transcriber=transcriber, verifier=verifier, clock=clock)
    app.state.session_store = store
    app.state.deps = deps
    app.state.payments = payments
    app.state.agenda_path = agenda_path
    app.state.pin_validator = pin_validator

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[CORS_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["X-Request-Id", "Content-Type"],
    )

    @app.middleware("http")
    async def safe_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000)
        entry = {
            "requestId": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "durationMs": duration_ms,
        }
        state = getattr(request.state, "turn_state", None)
        if state:
            entry["state"] = state
        logger.info(json.dumps(entry, ensure_ascii=False))
        response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(SessionNotFound)
    async def session_not_found_handler(request: Request, exc: SessionNotFound):
        return _error(404, "SESSION_NOT_FOUND", "La sesión no existe")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "INVALID_REQUEST", "La petición no es válida")

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return _error(400, "INVALID_REQUEST", "La petición no es válida")

    # ---------------------------------------------------------------- enrollment
    @app.post("/api/enrollment", status_code=201)
    async def post_enrollment(request: Request, consent: str = Form(""), audio: list[UploadFile] = File(default=[])):
        if consent != "true":
            return _error(400, "CONSENT_REQUIRED", "Falta el consentimiento explícito")
        if len(audio) != 3:
            return _error(400, "SAMPLES_REQUIRED", "Se necesitan tres muestras de voz")
        enrolled["value"] = True  # solo la marca; el audio se descarta en el esqueleto
        return {"enrolled": True}

    @app.get("/api/enrollment")
    async def get_enrollment():
        return {"enrolled": enrolled["value"]}

    # ---------------------------------------------------------------- budget
    @app.post("/api/budget", status_code=201)
    async def post_budget(request: Request, body: dict = Body(...)):
        amount = body.get("debitAmount")
        if not _valid_amount(amount):
            return _error(400, "INVALID_AMOUNT", "El monto no es válido")
        interval = body.get("interval")
        if interval is not None and not isinstance(interval, str):
            return _error(400, "INVALID_AMOUNT", "El monto no es válido")
        budget["limit"] = amount
        budget["interval"] = interval
        session = store.create()
        session.state = TurnState.AWAITING_AUTHORIZATION  # esperando la aprobación en la wallet
        session.pending_authorization = True
        return {"interactUrl": PLACEHOLDER_INTERACT_URL}

    @app.get("/api/budget")
    async def get_budget():
        limit = budget.get("limit") or {"value": "0", "assetCode": asset_code(), "assetScale": asset_scale()}
        entry = {"debitAmount": limit}
        if budget.get("interval"):
            entry["interval"] = budget["interval"]
        return {
            "status": "PENDING",
            "limit": entry,
            "spent": _zero_amount(limit),
            "remaining": _zero_amount(limit),
        }

    # ---------------------------------------------------------------- grant-callback
    @app.post("/api/grant-callback")
    async def post_grant_callback(request: Request, body: dict = Body(...)):
        session = store.take_pending_authorization()
        has_params = isinstance(body.get("interactRef"), str) and isinstance(body.get("hash"), str)
        if session and has_params:
            session.state = TurnState.AWAITING_COMMAND
            request.state.turn_state = TurnState.AWAITING_COMMAND.value
            return turn_logic.response(session.id, TurnState.AWAITING_COMMAND, turn_logic.SAY_AUTHORIZED)
        if session:
            session.state = TurnState.REJECTED
        request.state.turn_state = TurnState.REJECTED.value
        session_id = session.id if session else "unknown"
        return turn_logic.response(session_id, TurnState.REJECTED, turn_logic.SAY_REJECTED)

    # ---------------------------------------------------------------- turns
    @app.post("/api/turns")
    async def post_turns(
        request: Request,
        sessionId: str = Form(""),
        audio: UploadFile | None = File(default=None),
        text: str = Form(""),
        kind: str = Form(""),
    ):
        if kind == "verify_pending":
            if audio is not None or text or not sessionId:
                return _error(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno")
            session = store.get(sessionId)
            session.state = TurnState.PAYMENT_PENDING
            request.state.turn_state = TurnState.PAYMENT_PENDING.value
            return turn_logic.response(session.id, TurnState.PAYMENT_PENDING, turn_logic.SAY_PENDING)

        if (audio is None) == (not text):
            return _error(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno")

        session: Session = store.get(sessionId) if sessionId else store.create()

        audio_bytes = audio.file.read() if audio is not None else None
        result = handle_turn(session, audio_bytes, text, deps)
        request.state.turn_state = result["state"]
        return result

    return app


app = create_app()
