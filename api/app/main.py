"""Rutas del Contrato B (`openapi/contract-b.yaml`) sobre el orquestador.

Arranque, desde `api/`: `uvicorn app.main:app --port 8000`. Logs de cada request: solo
requestId, ruta, estado HTTP, `state` del turno y duración; nunca el cuerpo (ni audio, ni texto,
ni el PIN).
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from payments_client import PaymentsClient

from .config import load_settings
from .orchestrator import ApiFailure, Orchestrator
from .voice_io import TranscriptionUnavailable, VoiceIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ezpay.api")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(orchestrator: Orchestrator | None = None, voice_io: VoiceIO | None = None) -> FastAPI:
    settings = load_settings()
    state = {"orchestrator": orchestrator, "voice": voice_io}

    @asynccontextmanager
    async def lifespan(_app):
        if state["voice"] is None:
            state["voice"] = VoiceIO()
            state["voice"].load(warmup_local=settings.warmup_local_whisper)
        if state["orchestrator"] is None:
            payments = PaymentsClient(node_base_url=settings.node_base_url, asset_code=settings.asset_code,
                                      asset_scale=settings.asset_scale)
            state["orchestrator"] = Orchestrator(settings, payments, state["voice"])
        logger.info("EZPAY api ready (node=%s, speaker=%s, wallet=%s)", settings.node_base_url,
                    "ready" if state["voice"].speaker_ready else "unavailable",
                    "configured" if settings.wallet_address else "MISSING")
        yield

    app = FastAPI(title="EZPAY Contract B", version="1.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Request-Id"], expose_headers=["X-Request-Id"])

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.rid = rid
        request.state.turn_state = None
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error requestId=%s path=%s", rid, request.url.path)
            response = _error(500, "INTERNAL_ERROR", "Error interno")
        response.headers["X-Request-Id"] = rid
        logger.info("requestId=%s %s %s status=%s state=%s ms=%d", rid, request.method, request.url.path,
                    response.status_code, request.state.turn_state or "-", (time.monotonic() - started) * 1000)
        return response

    @app.exception_handler(ApiFailure)
    async def api_failure(_request: Request, exc: ApiFailure):
        return _error(exc.status, exc.code, exc.message)

    def orch() -> Orchestrator:
        return state["orchestrator"]

    # ------------------------------------------------------------- turnos
    @app.post("/api/turns")
    async def create_turn(request: Request):
        try:
            form = await request.form(max_part_size=MAX_UPLOAD_BYTES)
        except Exception:
            raise ApiFailure(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno") from None
        try:
            session_id = form.get("sessionId") or None
            text = form.get("text")
            kind = form.get("kind")
            audio_part = form.get("audio")
            audio = None
            if isinstance(audio_part, UploadFile):
                audio = await audio_part.read()
            elif isinstance(audio_part, str):
                raise ApiFailure(400, "INVALID_AUDIO", "El audio no se pudo leer")
        finally:
            await form.close()
        if text is not None and not isinstance(text, str):
            raise ApiFailure(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno")
        if isinstance(text, str) and not text.strip():
            text = None
        result = await run_in_threadpool(orch().turn, session_id=session_id, text=text, audio=audio,
                                         kind=kind if isinstance(kind, str) else None, request_id=request.state.rid)
        request.state.turn_state = result.session.state.value
        return result.to_dict()

    @app.post("/api/grant-callback")
    async def grant_callback(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        clean = {k: body[k] for k in ("interactRef", "hash", "result") if isinstance(body.get(k), str)}
        result = await run_in_threadpool(orch().grant_callback, clean, request.state.rid)
        request.state.turn_state = result.session.state.value
        return result.to_dict()

    # ------------------------------------------------------------ presupuesto
    @app.post("/api/budget", status_code=201)
    async def create_budget(request: Request):
        try:
            body = await request.json()
        except Exception:
            raise ApiFailure(400, "INVALID_AMOUNT", "El monto no es válido") from None
        if not isinstance(body, dict):
            raise ApiFailure(400, "INVALID_AMOUNT", "El monto no es válido")
        interval = body.get("interval") if isinstance(body.get("interval"), str) else None
        url = await run_in_threadpool(orch().create_budget, body.get("debitAmount"), interval, request.state.rid)
        return {"interactUrl": url}

    @app.get("/api/budget")
    async def get_budget(request: Request):
        return await run_in_threadpool(orch().get_budget, request.state.rid)

    # ----------------------------------------------------------- enrolamiento
    @app.get("/api/enrollment")
    async def get_enrollment():
        return {"enrolled": state["voice"].enrolled()}

    @app.post("/api/enrollment", status_code=201)
    async def enroll(request: Request):
        try:
            form = await request.form(max_part_size=MAX_UPLOAD_BYTES)
        except Exception:
            raise ApiFailure(400, "SAMPLES_REQUIRED", "Se necesitan tres muestras de voz") from None
        try:
            if form.get("consent") != "true":
                raise ApiFailure(400, "CONSENT_REQUIRED", "Falta el consentimiento explícito")
            parts = [p for p in form.getlist("audio") if isinstance(p, UploadFile)]
            if len(parts) != 3:
                raise ApiFailure(400, "SAMPLES_REQUIRED", "Se necesitan tres muestras de voz")
            raw = [await p.read() for p in parts]
        finally:
            await form.close()
        return await run_in_threadpool(_enroll, state["voice"], raw)

    return app


def _enroll(voice: VoiceIO, raw: list[bytes]) -> dict:
    from speaker import EnrollmentError
    from voice.transcribe import TranscribeInputError

    if voice.enrollment is None or not voice.speaker_ready:
        logger.error("Enrollment requested but the speaker model is not available")
        raise ApiFailure(500, "INTERNAL_ERROR", "Error interno")
    try:
        samples = [voice.decode(b) for b in raw]
    except (TranscribeInputError, TranscriptionUnavailable):
        raise ApiFailure(400, "INVALID_AUDIO", "Una de las muestras no se pudo leer") from None
    try:
        return voice.enrollment.enroll(samples, consent=True)
    except EnrollmentError as err:
        messages = {
            "CONSENT_REQUIRED": "Falta el consentimiento explícito",
            "SAMPLES_REQUIRED": "Se necesitan tres muestras de voz",
            "INVALID_AUDIO": "Una de las muestras no se pudo leer",
            "INCONSISTENT_SAMPLES": "Las muestras no parecen de la misma voz",
        }
        raise ApiFailure(400, err.code, messages.get(err.code, err.code)) from None


app = create_app()
