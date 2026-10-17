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
from voice.replies import Reply, classify_reply

from payments_client import PaymentPending, PaymentsError, UpstreamUnavailable

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
        store=None,
    ) -> None:
        self.transcriber = transcriber
        self.verifier = verifier
        self.clock = clock or UtcClock()
        self.payments = payments
        self.agenda = load_agenda(agenda_path or AGENDA_PATH)
        self.pin_validator = pin_validator or default_validator
        self.store = store
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
            self.log_node_defect(exc, request_id)
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
    def _check_pending_payment(self, session, request_id) -> None:
        """Verificación del pago pendiente antes de procesar el turno (payments-client).

        COMPLETED → registra el historial y libera el bloqueo; FAILED → libera
        también (el pago anterior falló); PROCESSING → sigue pendiente.
        """
        pending = session.pending_payment
        payment_id = pending.get("paymentId") if pending else None
        if not payment_id:
            return
        final = self._node_call(
            "get_payment",
            lambda: self.payments.get_payment(payment_id, request_id=request_id),
            request_id,
        )
        if final["status"] in ("COMPLETED", "FAILED"):
            wallet = pending.get("recipient")
            if final["status"] == "COMPLETED" and wallet:
                self.history.add(wallet)
            session.pending_payment = None

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

        self._check_pending_payment(session, request_id)
        intent = intent_dict(transcript)
        resolution = resolution_dict(intent, self.agenda)
        voice_status, voice_score = self._voice_of(audio_bytes, text)
        enrolled = bool(self.verifier.enrollment_status()) if self.verifier else False
        return self._decide_command(session, intent, resolution, voice_status, voice_score,
                                    transcript=transcript, audio_bytes=audio_bytes, text=text,
                                    request_id=request_id)

    def _decide_command(self, session, intent, resolution, voice_status, voice_score, *,
                        transcript=None, audio_bytes=None, text=None, request_id=None) -> dict:
        """La quote se pide antes del motor (excepción SEG-1: sin presupuesto, quote null)."""
        intent, resolution = self._with_history(intent, resolution)
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
            enrolled=bool(self.verifier.enrollment_status()) if self.verifier else False,
            has_budget_grant=has_budget,
            quote=quote,
            pending_payment=self._pending_of(session),
            clock=self.clock,
            agenda=self.agenda,
        )
        return self._apply_decision(session, context, client_quote=quote, transcript=transcript, audio_bytes=audio_bytes, text=text, request_id=request_id)

    def _with_history(self, intent, resolution):
        """D9: un destinatario con pago COMPLETED previo entra como previouslyPaid."""
        if resolution.get("kind") == Kind.RESOLVED.value:
            wallet = resolution["contact"]["walletAddress"]
            if wallet in self.history:
                resolution = {**resolution, "contact": {**resolution["contact"], "previouslyPaid": True}}
        return intent, resolution

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

    def create_budget_grant(self, debit_value: str, interval: str | None, request_id: str | None) -> dict:
        """Crea el grant de presupuesto con el cliente de Node; el grantId queda en la app."""
        grant = self._node_call(
            "create_grant",
            lambda: self.payments.create_grant(
                DEMO_USER_ID,
                _wallet_address(),
                f"{FRONTEND_ORIGIN}/grant-callback",
                debit_value,
                interval=interval,
                request_id=request_id,
            ),
            request_id,
        )
        self.budget_grant_id = grant["grantId"]
        self.budget_status = "PENDING"
        return grant

    # -------------------------------------------------------------- callback
    def handle_callback(self, body: dict, request_id: str | None) -> dict:
        """POST /grant-callback: reenvía interactRef/hash verbatim a /continue (B-1).

        Sin interactRef o sin hash NO se llama a /continue: REJECTED. Los errores
        de Node (INVALID_HASH, GRANT_NOT_PENDING, GRANT_REJECTED) son fail-closed:
        REJECTED sin pagar (D-n 4 del reporte). La sesión pendiente se busca por
        grantId cuando el frontend lo reenvía; si no, por estado único pendiente.
        """
        interact_ref = body.get("interactRef")
        hash_value = body.get("hash")
        session = self.store.take_pending_authorization(body.get("grantId"))
        if session is None:
            return turns.response("unknown", TurnState.REJECTED, self._say(S.AUTH_REJECTED.value))
        kind = session.pending_authorization
        session.pending_authorization = None
        if not isinstance(interact_ref, str) or not isinstance(hash_value, str):
            session.state = TurnState.REJECTED
            self._clear_pending(session)
            return turns.response(session.id, TurnState.REJECTED, self._say(S.AUTH_REJECTED.value))
        try:
            self._node_call(
                "continue_grant",
                lambda: self.payments.continue_grant(session.grant_id, interact_ref, hash_value, request_id=request_id),
                request_id,
            )
        except UpstreamUnavailable:
            raise
        except PaymentsError as exc:
            self.log_node_defect(exc, request_id)
            session.state = TurnState.REJECTED
            self._clear_pending(session)
            return turns.response(session.id, TurnState.REJECTED, self._say(S.AUTH_REJECTED.value))
        if kind == "budget":
            self.budget_status = "ACTIVE"
            session.state = TurnState.AWAITING_COMMAND
            return turns.response(session.id, TurnState.AWAITING_COMMAND, self._say(S.AUTH_APPROVED.value))
        if kind == "one_off":
            return self._continue_one_off(session, request_id)
        return turns.response(session.id, TurnState.AWAITING_COMMAND, self._say(S.AUTH_APPROVED.value))

    # ------------------------------------------------------------- fase de pago
    def _confirmation_turn(self, session, audio_bytes, text, request_id) -> dict:
        """D4: la voz del "sí" se transcribe (para clasificar la respuesta) pero NO se
        vuelve a verificar; el context conserva la verificación del comando."""
        reply_text = text
        if audio_bytes is not None:
            reply_text = self.transcriber.transcribe(audio_bytes) if self.transcriber else None
        reply = classify_reply(reply_text)
        context = build_context(
            phase="CONFIRMATION",
            input_text=reply_text,
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
            reply=reply.value,
            unclear_replies=session.unclear_replies,
        )
        context_obj = parse_context(context)
        decision = engine_decide(context_obj)
        situation = engine_say_situation(decision, context_obj)
        if decision.decision is DecisionType.PAY:
            return self._pay(session, transcript=reply_text, request_id=request_id)
        if decision.decision is DecisionType.REQUIRE_AUTH:
            return self._require_one_off(session, context["quote"]["debitAmount"], reply_text, request_id)
        if decision.decision is DecisionType.ASK_CONFIRM:
            # repregunta una vez (SEG-2): el contador vive en la sesión
            session.state = TurnState.AWAITING_CONFIRMATION
            session.unclear_replies = session.unclear_replies + 1
            return turns.response(
                session.id, TurnState.AWAITING_CONFIRMATION,
                self._say(situation, contact=session.contact, quote=session.quote),
                transcript=reply_text,
            )
        # REJECT: USER_DECLINED o REPLY_UNCLEAR_REJECTED
        session.state = TurnState.REJECTED
        self._clear_pending(session)
        self._cancel_one_off_silent(session, request_id)
        return turns.response(session.id, TurnState.REJECTED, self._say(situation), transcript=reply_text)

    def _require_one_off(self, session, debit_amount, transcript, request_id) -> dict:
        """El grant puntual del exceso: R1/<instante de la solicitud en UTC>/P1W."""
        grant = self._request_one_off(session, debit_amount, request_id)
        session.state = TurnState.AWAITING_AUTHORIZATION
        return turns.response(
            session.id, TurnState.AWAITING_AUTHORIZATION,
            self._say(S.AUTH_REDIRECT.value),
            transcript=transcript,
            interact_url=grant["interactUrl"],
        )

    def _request_one_off(self, session, debit_amount: dict, request_id: str | None) -> dict:
        from payments_client import one_off_interval

        interval = one_off_interval(self.clock.now())
        grant = self._node_call(
            "create_grant",
            lambda: self.payments.create_grant(
                DEMO_USER_ID,
                _wallet_address(),
                f"{FRONTEND_ORIGIN}/grant-callback",
                debit_amount["value"],
                interval=interval,
                request_id=request_id,
            ),
            request_id,
        )
        session.pending_authorization = "one_off"
        session.grant_id = grant["grantId"]
        session.one_off_grant_id = grant["grantId"]
        return grant

    def _continue_one_off(self, session, request_id) -> dict:
        """El callback del grant puntual: recotiza con su grantId y paga si la quote entra."""
        intent = session.intent
        contact = session.contact
        try:
            quote = self._node_call(
                "create_quote",
                lambda: self.payments.create_quote(
                    session.grant_id,
                    contact["walletAddress"],
                    intent["amount"]["value"],
                    request_id=request_id,
                ),
                request_id,
            )
        except PaymentsError as exc:
            self.log_node_defect(exc, request_id)
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        session.quote = quote
        if quote["exceedsRemaining"]:
            # el débito cambió: cancela el puntual y pide otro (el say no menciona costos)
            self._cancel_one_off_silent(session, request_id)
            grant = self._request_one_off(session, quote["debitAmount"], request_id)
            session.state = TurnState.AWAITING_AUTHORIZATION
            return turns.response(
                session.id, TurnState.AWAITING_AUTHORIZATION,
                self._say(S.AUTH_REDIRECT.value),
                interact_url=grant["interactUrl"],
            )
        session.idempotency_key = None  # quote nueva: clave nueva
        return self._pay(session, transcript=None, request_id=request_id)

    def _pay(self, session, *, transcript=None, request_id=None) -> dict:
        """Paga la quote de la sesión: una Idempotency-Key por quote, reintentos con la misma."""
        quote = session.quote
        if not quote:
            raise TurnError(500, "INTERNAL_ERROR", "Error interno")
        key = session.idempotency_key or str(uuid.uuid4())
        session.idempotency_key = key
        try:
            outcome = self._node_call(
                "create_payment",
                lambda: self.payments.create_payment(quote["quoteId"], key, request_id=request_id),
                request_id,
            )
        except UpstreamUnavailable:
            raise
        except PaymentsError as exc:
            if exc.code in ("LIMIT_EXCEEDED", "GRANT_INVALID"):
                # reautorización puntual (payments-client): el turno pasa a AWAITING_AUTHORIZATION
                return self._require_one_off(session, quote["debitAmount"], transcript, request_id)
            self.log_node_defect(exc, request_id)
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        return self._settle_payment(session, outcome, transcript=transcript, request_id=request_id)

    def _settle_payment(self, session, outcome, *, transcript=None, request_id=None) -> dict:
        if isinstance(outcome, PaymentPending):
            # resultado incierto sin paymentId: PAYMENT_PENDING, nunca rechazo
            session.pending_payment = {
                "recipient": session.contact["walletAddress"] if session.contact else "",
                "createdAt": self.clock.now().isoformat(),
                "status": "PROCESSING",
                "paymentId": None,
                "quoteId": session.quote["quoteId"],
                "idempotencyKey": session.idempotency_key,
            }
            session.state = TurnState.PAYMENT_PENDING
            return turns.response(
                session.id, TurnState.PAYMENT_PENDING, self._say(S.PAYMENT_PENDING.value), transcript=transcript,
            )
        session.pending_payment = {
            "recipient": session.contact["walletAddress"] if session.contact else "",
            "createdAt": self.clock.now().isoformat(),
            "status": "PROCESSING",
            "paymentId": outcome["paymentId"],
            "quoteId": session.quote["quoteId"],
            "idempotencyKey": session.idempotency_key,
            "debitAmount": outcome["debitAmount"],
        }
        session.payment_id = outcome["paymentId"]
        if outcome["status"] == "FAILED":
            return self._payment_rejected(session)
        if outcome["status"] == "COMPLETED":
            return self._payment_completed(session, outcome, transcript=transcript, request_id=request_id)
        final = self._node_call(
            "wait_for_payment",
            lambda: self.payments.wait_for_payment(outcome["paymentId"], request_id=request_id),
            request_id,
        )
        return self._resolve_final(session, final, outcome, transcript=transcript, request_id=request_id)

    def _resolve_final(self, session, final, created, *, transcript=None, request_id=None) -> dict:
        if isinstance(final, PaymentPending):
            session.state = TurnState.PAYMENT_PENDING
            return turns.response(
                session.id, TurnState.PAYMENT_PENDING,
                self._say(S.PAYMENT_PENDING.value),
                transcript=transcript,
                payment=self._payment_object(session, created["paymentId"], created["debitAmount"]),
            )
        if final["status"] == "COMPLETED":
            return self._payment_completed(session, created, transcript=transcript, request_id=request_id)
        return self._payment_rejected(session)

    def _payment_completed(self, session, created, *, transcript=None, request_id=None) -> dict:
        session.state = TurnState.COMPLETED
        wallet = session.contact["walletAddress"] if session.contact else None
        if wallet:
            self.history.add(wallet)  # historial de pagos por destinatario (D9, R7)
        session.pending_payment = None
        self._cancel_one_off_silent(session, request_id)
        receive = session.quote["receiveAmount"]
        debit = created["debitAmount"]
        return turns.response(
            session.id, TurnState.COMPLETED,
            voice_say(S.COMPLETED, amount=self._voice_amount(receive), name=session.contact["name"],
                      debit=self._voice_amount(debit) if debit else None),
            transcript=transcript,
            payment=self._payment_object(session, created["paymentId"], debit),
        )

    def _payment_rejected(self, session) -> dict:
        """Pago FAILED (marca de Open Payments): REJECTED. Sin plantilla de fallo en el
        catálogo de Voz (D-n 2 del reporte): fail-closed con la plantilla más próxima."""
        session.state = TurnState.REJECTED
        session.pending_payment = None
        return turns.response(session.id, TurnState.REJECTED, self._say(S.REPLY_UNCLEAR_REJECTED.value))

    def _payment_object(self, session, payment_id: str, debit_amount: dict | None) -> dict:
        return {
            "paymentId": payment_id,
            "receiver": session.contact["walletAddress"] if session.contact else "",
            "debitAmount": debit_amount or session.quote["debitAmount"],
            "receiveAmount": session.quote["receiveAmount"],
        }

    def _cancel_one_off_silent(self, session, request_id: str | None) -> None:
        """Cancelar el grant puntual no bloquea el turno: se registra y sigue."""
        grant_id = session.one_off_grant_id
        if not grant_id:
            return
        session.one_off_grant_id = None
        try:
            self._node_call(
                "cancel_grant",
                lambda: self.payments.cancel_grant(grant_id, request_id=request_id),
                request_id,
            )
        except (UpstreamUnavailable, PaymentsError) as exc:
            code = exc.code if isinstance(exc, PaymentsError) else "UPSTREAM_UNAVAILABLE"
            _logger.info(json.dumps({
                "event": "orchestrator_error", "op": "cancel_grant", "code": code, "requestId": request_id,
            }, ensure_ascii=False))

    # ------------------------------------------------------ verificación pendiente
    def verify_pending(self, session, request_id: str | None) -> dict:
        """El turno automático de B-2: consulta el pago pendiente de la sesión.

        COMPLETED → lo informa; FAILED → informa el fallo; PROCESSING → sigue
        pendiente. Sin paymentId reintenta POST /payments con la MISMA clave.
        """
        pending = session.pending_payment
        if not pending:
            session.state = TurnState.PAYMENT_PENDING
            return turns.response(session.id, TurnState.PAYMENT_PENDING, self._say(S.PAYMENT_PENDING.value))
        payment_id = pending.get("paymentId")
        if payment_id:
            final = self._node_call(
                "get_payment",
                lambda: self.payments.get_payment(payment_id, request_id=request_id),
                request_id,
            )
            created = {"paymentId": payment_id, "debitAmount": pending.get("debitAmount")}
            if final["status"] == "COMPLETED":
                return self._payment_completed(session, created, request_id=request_id)
            if final["status"] == "FAILED":
                return self._payment_rejected(session)
            session.state = TurnState.PAYMENT_PENDING
            return turns.response(
                session.id, TurnState.PAYMENT_PENDING,
                self._say(S.PAYMENT_PENDING.value),
                payment=self._payment_object(session, payment_id, pending.get("debitAmount")),
            )
        # reintentos agotados sin 201: la misma clave y la misma quote
        key = pending["idempotencyKey"]
        try:
            outcome = self._node_call(
                "create_payment",
                lambda: self.payments.create_payment(pending["quoteId"], key, request_id=request_id),
                request_id,
            )
        except UpstreamUnavailable:
            raise
        except PaymentsError as exc:
            self.log_node_defect(exc, request_id)
            raise TurnError(500, "INTERNAL_ERROR", "Error interno") from None
        return self._settle_payment(session, outcome, transcript=None, request_id=request_id)

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
                grant = self.create_budget_grant(intent["amount"]["value"], None, request_id)
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
            # CONFIRMED_NEEDS_WALLET_AUTH: grant puntual del exceso (R6)
            return self._require_one_off(session, context["quote"]["debitAmount"], transcript, request_id)

        if decision.decision is DecisionType.PAY:
            return self._pay(session, transcript=transcript, request_id=request_id)

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

    def log_node_defect(self, exc: PaymentsError, request_id: str | None) -> None:
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

    # ------------------------------------------------ elección de destinatario
    def _choice_turn(self, session, audio_bytes, text, request_id) -> dict:
        """B-4: la elección vuelve como text = alias, o por voz resuelta SOLO contra las options."""
        transcript: str | None = text or None
        if audio_bytes is not None:
            transcript = self.transcriber.transcribe(audio_bytes) if self.transcriber else None
            if not transcript:
                return self._reask_choice(session, None)
        from voice.contacts import Option, resolve_choice

        offered = [Option(o["alias"], o["name"]) for o in (session.options or [])]
        resolution = resolve_choice(transcript, offered, self.agenda)
        if resolution.kind is not Kind.RESOLVED:
            return self._reask_choice(session, transcript)
        session.contact = resolution.contact.to_dict()
        session.options = None
        # el comando continúa con el contacto resuelto; la voz es la del comando (D4)
        voice = session.voice or {"status": "NOT_AVAILABLE", "score": None}
        return self._decide_command(
            session,
            session.intent,
            {"kind": Kind.RESOLVED.value, "contact": session.contact},
            voice["status"],
            voice.get("score"),
            transcript=transcript,
            audio_bytes=audio_bytes,
            text=text,
            request_id=request_id,
        )

    def _reask_choice(self, session, transcript) -> dict:
        session.state = TurnState.AWAITING_RECIPIENT_CHOICE
        options = [dict(o) for o in (session.options or [])]
        return turns.response(
            session.id, TurnState.AWAITING_RECIPIENT_CHOICE,
            self._say(S.CHOICE.value, options=options),
            transcript=transcript,
            options=options,
        )

