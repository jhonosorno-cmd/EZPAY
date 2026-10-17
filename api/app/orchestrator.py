"""Orquestador del turno (spec turn-orchestration): intención (Voz) → agenda →
verificación de voz → quote con el cliente de Node → motor de decisión →
transición de TurnState → llamadas a Node.

R3: fase de comando (texto y audio) hasta cada decisión del motor, con la tabla
de transiciones y los `say` del catálogo de Voz. La quote se pide antes del
motor (excepción SEG-1: sin grant de presupuesto, quote null). El PIN, el pago
y el callback se implementan en las rebanadas siguientes.
"""
from __future__ import annotations

import json
import logging
import os
import uuid

from decision import (
    DecisionType,
    InvalidContextError,
    decide as engine_decide,
    parse_context,
    say_situation as engine_say_situation,
)
from pin.pin import PinValidator, default_validator
from voice.amounts import Amount as VoiceAmount
from voice.contacts import Kind, load_agenda, resolve_choice, resolve_recipient
from voice.config import AGENDA_PATH
from voice.phrases import S, say as voice_say
from voice.replies import classify_reply

from payments_client import PaymentsError, UpstreamUnavailable

from .config import asset_code, asset_scale
from .engine_context import build_context, intent_dict, resolution_dict
from .ports import UtcClock
from .states import TurnState
from . import turns

DEMO_USER_ID = "demo-user"
FRONTEND_ORIGIN = "http://localhost:5173"
PENDING_WINDOW_SECONDS = 120  # propuesta de Pagos en turn-orchestration; ML 2 confirma el umbral

_logger = logging.getLogger("api.app")


class TurnError(Exception):
    """El turno no puede continuar: estado HTTP y código del Contrato B, sin datos del request."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _wallet_address() -> str:
    """Wallet emisora de la demo: solo del entorno (es la wallet que autoriza el grant)."""
    return os.environ.get("EZPAY_WALLET_ADDRESS", "https://ilp.interledger-test.dev/marta")


class Orchestrator:
    def __init__(
        self,
        *,
        transcriber=None,
        verifier=None,
        clock=None,
        payments=None,
        agenda_path=None,
        pin_validator=None,
    ) -> None:
        self.transcriber = transcriber
        self.verifier = verifier
        self.clock = clock or UtcClock()
        self.payments = payments
        self.agenda = load_agenda(agenda_path or AGENDA_PATH)
        self.pin_validator = pin_validator or default_validator
        self.budget_grant_id: str | None = None
        self.budget_status: str | None = None
        self.history: set[str] = set()  # wallets con pago COMPLETED (D9, R7)
        self._current_op: str | None = None

    # ------------------------------------------------------------------ turnos
    def _node_call(self, op: str, fn, request_id: str | None):
        """Llama a Node registrando la operación en curso (para logs sin cuerpos)."""
        self._current_op = op
        return fn()

    def handle_turn(self, session, *, audio_bytes=None, text=None, request_id=None) -> dict:
        try:
            return self._dispatch(session, audio_bytes, text, request_id)
        except UpstreamUnavailable:
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        except PaymentsError as exc:
            self._log_node_defect(exc, request_id)
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        except InvalidContextError:
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        finally:
            self._current_op = None

    def _dispatch(self, session, audio_bytes, text, request_id) -> dict:
        if session.state is TurnState.AWAITING_PIN:
            return self._pin_turn(session, audio_bytes, text, request_id)
        if session.state is TurnState.AWAITING_RECIPIENT_CHOICE:
            return self._choice_turn(session, audio_bytes, text, request_id)
        if session.state is TurnState.AWAITING_CONFIRMATION:
            return self._confirmation_turn(session, audio_bytes, text, request_id)
        return self._command_turn(session, audio_bytes, text, request_id)

    # ---------------------------------------------------------- fase de comando
    def _command_turn(self, session, audio_bytes, text, request_id) -> dict:
        transcript: str | None = text or None
        if audio_bytes is not None:
            transcript = self.transcriber.transcribe(audio_bytes) if self.transcriber else None
            if not transcript:
                # sin transcripción no hay intención: REASK determinista, sin proveedores externos
                session.state = TurnState.AWAITING_COMMAND
                return turns.response(session.id, TurnState.AWAITING_COMMAND, self._say(S.NOT_UNDERSTOOD.value))
        if not audio_bytes and transcript and turns.is_digits(transcript):
            # dígitos (4 a 6) fuera de AWAITING_PIN: nunca llegan a la extracción de intención
            session.state = TurnState.AWAITING_COMMAND
            return turns.response(session.id, TurnState.AWAITING_COMMAND, self._say(S.NOT_UNDERSTOOD.value))

        intent = intent_dict(transcript)
        resolution = resolution_dict(intent, self.agenda)
        voice_status, voice_score = self._voice_of(audio_bytes, text)
        enrolled = bool(self.verifier.enrollment_status()) if self.verifier else False
        has_budget = self._has_active_budget()
        quote = None
        if (
            has_budget
            and intent["action"] == "PAY"
            and intent["status"] == "OK"
            and intent["amount"] is not None
            and intent["recipient"] is not None
            and resolution["kind"] == Kind.RESOLVED.value
        ):
            quote = self._node_call(
                "create_quote",
                lambda: self.payments.create_quote(
                    self.budget_grant_id,
                    resolution["contact"]["walletAddress"],
                    intent["amount"]["value"],
                    request_id=request_id,
                ),
                request_id,
            )
        context = build_context(
            phase="COMMAND",
            input_text=transcript,
            intent=intent,
            resolution=resolution,
            voice_status=voice_status,
            voice_score=voice_score,
            enrolled=enrolled,
            has_budget_grant=has_budget,
            quote=quote,
            pending_payment=self._pending_of(session),
            clock=self.clock,
            agenda=self.agenda,
        )
        return self._apply_decision(session, context, client_quote=quote, transcript=transcript, audio_bytes=audio_bytes, text=text, request_id=request_id)

    def _voice_of(self, audio_bytes, text) -> tuple[str, float | None]:
        """Regla de ML 2: un comando por texto entra NOT_AVAILABLE; el audio va al verificador."""
        if audio_bytes is None:
            return "NOT_AVAILABLE", None
        if self.verifier is None:
            return "NOT_AVAILABLE", None
        status, score = self.verifier.verify(audio_bytes)
        return status, score

    def _has_active_budget(self) -> bool:
        return self.budget_grant_id is not None and self.budget_status == "ACTIVE"

    def _pending_of(self, session) -> dict | None:
        if not session.pending_payment:
            return None
        return {
            "recipient": session.pending_payment["recipient"],
            "createdAt": session.pending_payment["createdAt"],
            "status": session.pending_payment["status"],
        }

    # -------------------------------------------------- decisión y transiciones
    def _apply_decision(self, session, context, *, client_quote, transcript, audio_bytes, text, request_id) -> dict:
        context_obj = parse_context(context)
        decision = engine_decide(context_obj)
        situation = engine_say_situation(decision, context_obj)
        intent = context["intent"]
        resolution = context["resolution"]
        contact = resolution["contact"] if resolution["kind"] == Kind.RESOLVED.value else None
        state_kwargs: dict = {}

        if decision.decision is DecisionType.REJECT:
            session.state = TurnState.REJECTED
            self._clear_pending(session)
            return turns.response(session.id, TurnState.REJECTED, self._say(situation, contact=contact, intent=intent))

        if decision.decision is DecisionType.REASK:
            session.state = TurnState.AWAITING_COMMAND
            shown = None if (not audio_bytes and text and turns.is_digits(text)) else transcript
            return turns.response(
                session.id, TurnState.AWAITING_COMMAND,
                self._say(situation, contact=contact, intent=intent),
                transcript=shown,
            )

        if decision.decision is DecisionType.ASK_RECIPIENT:
            session.state = TurnState.AWAITING_RECIPIENT_CHOICE
            options = [dict(o) for o in resolution["options"]]
            session.options = options
            session.intent = intent
            session.voice = {"status": context["voice"]["status"], "score": context["voice"]["score"]}
            session.unclear_replies = 0
            return turns.response(
                session.id, TurnState.AWAITING_RECIPIENT_CHOICE,
                self._say(situation, options=options),
                transcript=transcript, options=options,
            )

        if decision.decision is DecisionType.ASK_PIN:
            session.state = TurnState.AWAITING_PIN
            session.intent = intent
            session.contact = contact
            session.quote = client_quote
            session.voice = {"status": context["voice"]["status"], "score": context["voice"]["score"]}
            session.enrolled = context["enrolled"]
            session.unclear_replies = 0
            return turns.response(session.id, TurnState.AWAITING_PIN, self._say(situation, contact=contact))

        if decision.decision is DecisionType.ASK_CONFIRM:
            session.state = TurnState.AWAITING_CONFIRMATION
            session.intent = intent
            session.contact = contact
            session.quote = client_quote
            session.voice = {"status": context["voice"]["status"], "score": context["voice"]["score"]}
            session.enrolled = context["enrolled"]
            session.unclear_replies = 0
            return turns.response(
                session.id, TurnState.AWAITING_CONFIRMATION,
                self._say(situation, contact=contact, quote=context["quote"]),
                transcript=transcript,
            )

        if decision.decision is DecisionType.REQUIRE_AUTH:
            if decision.reason.value == "NO_BUDGET_GRANT":
                grant = self._node_call(
                    "create_grant",
                    lambda: self.payments.create_grant(
                        DEMO_USER_ID,
                        _wallet_address(),
                        f"{FRONTEND_ORIGIN}/grant-callback",
                        intent["amount"]["value"],
                        interval=None,
                        request_id=request_id,
                    ),
                    request_id,
                )
                self.budget_grant_id = grant["grantId"]
                self.budget_status = "PENDING"
                session.grant_id = grant["grantId"]
                session.pending_authorization = "budget"
                session.intent = intent
                session.contact = contact
                session.state = TurnState.AWAITING_AUTHORIZATION
                return turns.response(
                    session.id, TurnState.AWAITING_AUTHORIZATION,
                    self._say(situation, contact=contact),
                    transcript=transcript,
                    interact_url=grant["interactUrl"],
                )
            # CONFIRMED_NEEDS_WALLET_AUTH: grant puntual (R6)
            raise TurnError(500, "INTERNAL_ERROR", "Error interno")

        # PAY: rebanada R6
        raise TurnError(500, "INTERNAL_ERROR", "Error interno")

    # ------------------------------------------------------------------- say
    def _say(self, situation_name: str, *, contact=None, intent=None, quote=None,
             options=None, remaining=None) -> str:
        situ = S(situation_name)
        params: dict = {}
        if situ in (S.CONFIRM, S.CONFIRM_UNCLEAR, S.PENDING_PAYMENT_UNCONFIRMED):
            params["amount"] = self._voice_amount(quote["receiveAmount"])
            params["name"] = contact["name"]
        elif situ in (S.NEW_RECIPIENT, S.PENDING_PAYMENT_SAME_RECIPIENT, S.PENDING_PAYMENT_UNCONFIRMED_OVERRUN, S.NEAR):
            params["name"] = contact["name"]
        elif situ is S.CHOICE:
            params["names"] = [o["name"] for o in options]
        elif situ is S.NOT_FOUND:
            params["spoken"] = intent["recipient"] or ""
        elif situ is S.TOO_MANY_DECIMALS:
            params["scale"] = asset_scale()
        elif situ is S.PIN_WRONG:
            params["remaining"] = remaining
        return voice_say(situ, **params)

    @staticmethod
    def _voice_amount(amount_dict: dict) -> VoiceAmount:
        return VoiceAmount(amount_dict["value"], amount_dict["assetCode"], amount_dict["assetScale"])

    def _log_node_defect(self, exc: PaymentsError, request_id: str | None) -> None:
        """INVALID_REQUEST de Node es defecto propio: se registra solo código y operación."""
        _logger.info(json.dumps({
            "event": "orchestrator_error",
            "op": self._current_op or "payments",
            "code": exc.code,
            "requestId": request_id,
        }, ensure_ascii=False))

    def _clear_pending(self, session) -> None:
        session.intent = None
        session.contact = None
        session.quote = None
        session.options = None
        session.voice = None
        session.unclear_replies = 0

    # ------------------------------------------------------------- fase de PIN
    def _pin_turn(self, session, audio_bytes, text, request_id) -> dict:
        """El PIN se valida SOLO en Python (componente de ML 2): nunca a Node, nunca a logs.

        El audio en AWAITING_PIN se descarta sin transcribir (spec); el texto es
        el PIN y entra como `pin` al context, sin tocar la extracción de intención.
        """
        if audio_bytes is not None:
            return turns.response(session.id, TurnState.AWAITING_PIN, self._say(S.PIN_KEYBOARD.value))
        validator = self.pin_validator or default_validator
        result = validator.verify(text or "", session.id)
        context = build_context(
            phase="PIN",
            input_text=None,
            intent=session.intent,
            resolution=self._stored_resolution(session),
            voice_status=session.voice["status"] if session.voice else "NOT_AVAILABLE",
            voice_score=session.voice.get("score") if session.voice else None,
            enrolled=session.enrolled,
            has_budget_grant=self._has_active_budget(),
            quote=session.quote,
            pending_payment=self._pending_of(session),
            clock=self.clock,
            agenda=self.agenda,
            reply=None,
            unclear_replies=0,
            pin_result=result,
        )
        context_obj = parse_context(context)
        decision = engine_decide(context_obj)
        situation = engine_say_situation(decision, context_obj)
        if decision.decision is DecisionType.ASK_CONFIRM:
            session.state = TurnState.AWAITING_CONFIRMATION
            session.unclear_replies = 0
            return turns.response(
                session.id, TurnState.AWAITING_CONFIRMATION,
                self._say(situation, contact=session.contact, quote=session.quote),
            )
        if decision.decision is DecisionType.ASK_PIN:
            session.state = TurnState.AWAITING_PIN
            return turns.response(
                session.id, TurnState.AWAITING_PIN,
                self._say(situation, remaining=result.remaining),
            )
        # REJECT: PIN_ATTEMPTS_EXHAUSTED o PIN_LOCKED; no se paga
        session.state = TurnState.REJECTED
        self._clear_pending(session)
        return turns.response(session.id, TurnState.REJECTED, self._say(situation))

    def _stored_resolution(self, session) -> dict | None:
        if session.contact is None:
            return None
        return {"kind": Kind.RESOLVED.value, "contact": session.contact}

    # --------------------------------------------- rebanadas siguientes (R5-R7)
    def _choice_turn(self, session, audio_bytes, text, request_id) -> dict:
        raise NotImplementedError("R7")

    def _confirmation_turn(self, session, audio_bytes, text, request_id) -> dict:
        raise NotImplementedError("R6")