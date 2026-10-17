"""Orquestador del turno (capabilities turn-orchestration y payments-client).

Flujo de un comando: intención (Voz) → agenda → verificación de voz (ML 2) → quote (Node) →
motor de decisión (ML 2) → TurnState y llamadas a Node. El motor decide; este módulo solo arma
el `context`, mapea la `Decision` a un `TurnState` y ejecuta lo que la decisión implica.

Reglas que cuida este módulo:
- El PIN solo se valida aquí (componente de ML 2) y nunca sale de Python, ni a logs (B-7).
- Solo se verifica la voz del comando, no la del "sí" (D4).
- Los `say` salen del catálogo de Voz (`voice/phrases.py`); los pocos textos sin plantilla están
  en `FALLBACK_SAY` y quedan pendientes de pasar al catálogo.
- Montos como strings de dígitos (CONV-1); moneda y escala desde la configuración.
"""
import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from decision import InvalidContextError, decide, parse_context, say_situation
from decision.models import DecisionType, Reason
from payments_client import PaymentPending, PaymentsError, UpstreamUnavailable, one_off_interval
from pin import verify_pin
from voice import phrases
from voice.amounts import Amount as VoiceAmount
from voice.amounts import AssetConfig
from voice.contacts import Kind, Resolution, load_agenda, resolve_choice, resolve_recipient
from voice.intents import extract_intent
from voice.replies import Reply, classify_reply

from .state import Command, PendingAuth, PendingPayment, Session, SessionStore, TurnState, WalletState
from .voice_io import NOT_AVAILABLE, VoiceIO

logger = logging.getLogger("ezpay.orchestrator")

_PIN_LIKE = re.compile(r"\s*[0-9]{4,6}\s*")

# Textos sin plantilla en voice/phrases.py todavía (pendiente: pasarlos al catálogo de Voz).
FALLBACK_SAY = {
    "PAYMENT_FAILED": "El envío falló. No se hizo ningún pago.",
    "BUDGET_APPROVED": "Listo, autorizaste tu presupuesto. ¿A quién le quieres enviar dinero?",
    "DEBIT_CHANGED": "El monto a debitar cambió. Necesito que lo autorices de nuevo en tu billetera.",
    "PENDING_COMPLETED": "Tu envío anterior ya llegó.",
}


class ApiFailure(Exception):
    """Error del Contrato B: se responde `{error: {code, message}}` con este status."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class TurnResult:
    session: Session
    say: str
    transcript: str | None = None
    interact_url: str | None = None
    options: list | None = None
    payment: dict | None = None

    def to_dict(self) -> dict:
        return {
            "sessionId": self.session.id,
            "state": self.session.state.value,
            "say": self.say,
            "transcript": self.transcript,
            "interactUrl": self.interact_url,
            "options": self.options,
            "payment": self.payment,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _vamount(amount: dict) -> VoiceAmount:
    return VoiceAmount(amount["value"], amount["assetCode"], amount["assetScale"])


class Orchestrator:
    def __init__(self, settings, payments, voice_io: VoiceIO, sessions: SessionStore | None = None,
                 wallet: WalletState | None = None, pin_verifier=verify_pin, clock=_now):
        self.settings = settings
        self.payments = payments
        self.voice = voice_io
        self.sessions = sessions or SessionStore()
        self.wallet = wallet or WalletState(settings.data_dir)
        self.agenda = load_agenda(settings.agenda_path)
        self.asset = AssetConfig(settings.asset_code, settings.asset_scale)
        self._verify_pin = pin_verifier
        self._clock = clock
        self._lock = threading.RLock()  # un turno a la vez: un solo usuario en el MVP

    # ================================================================ rutas
    def turn(self, *, session_id: str | None, text: str | None, audio: bytes | None, kind: str | None,
             request_id: str) -> TurnResult:
        with self._lock:
            return self._turn(session_id, text, audio, kind, request_id)

    def grant_callback(self, body: dict, request_id: str) -> TurnResult:
        with self._lock:
            return self._grant_callback(body, request_id)

    def create_budget(self, debit_amount: dict, interval: str | None, request_id: str) -> str:
        with self._lock:
            self._check_amount(debit_amount)
            grant = self._create_grant(debit_amount["value"], interval, request_id)
            self._replace_pending_auth(PendingAuth("budget", grant["grantId"], None), request_id)
            return grant["interactUrl"]

    def get_budget(self, request_id: str) -> dict:
        with self._lock:
            grant_id = self.wallet.budget_grant_id
            if grant_id is None and self.wallet.pending_auth and self.wallet.pending_auth.kind == "budget":
                grant_id = self.wallet.pending_auth.grant_id
            if grant_id is None:
                return self._no_budget()
            try:
                grant = self.payments.get_grant(grant_id, request_id=request_id)
            except PaymentsError as err:
                if err.code == "GRANT_NOT_FOUND":
                    self._forget_budget(grant_id)
                    return self._no_budget()
                raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None
            except UpstreamUnavailable:
                raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None
            return {"status": grant["status"], "limit": grant["limit"], "spent": grant["spent"],
                    "remaining": grant["remaining"]}

    def _no_budget(self) -> dict:
        """Sin grant: 200 válido contra el contrato (como el esqueleto de Pagos); el frontend trata
        todo estado distinto de ACTIVE como "sin presupuesto"."""
        zero = {"value": "0", "assetCode": self.settings.asset_code, "assetScale": self.settings.asset_scale}
        return {"status": "PENDING", "limit": {"debitAmount": zero}, "spent": zero, "remaining": zero}

    # ================================================================ turno
    def _turn(self, session_id, text, audio, kind, rid) -> TurnResult:
        if kind is not None:
            if kind != "verify_pending" or not session_id or text is not None or audio is not None:
                raise ApiFailure(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno")
        elif (text is None) == (audio is None):
            raise ApiFailure(400, "AUDIO_OR_TEXT_REQUIRED", "Envía audio o texto, no ambos ni ninguno")

        session = self.sessions.get(session_id) if session_id else None

        # Dígitos fuera de AWAITING_PIN (también con sesión perdida): nunca van a la intención.
        if text is not None and _PIN_LIKE.fullmatch(text) and (session is None or session.state is not TurnState.AWAITING_PIN):
            session = session or self.sessions.create()
            session.reset_command()
            session.state = TurnState.AWAITING_COMMAND
            return TurnResult(session, phrases.say(phrases.Situation.NOT_UNDERSTOOD))

        if session_id and session is None:
            raise ApiFailure(404, "SESSION_NOT_FOUND", "La sesión no existe")
        session = session or self.sessions.create()

        if kind == "verify_pending":
            return self._verify_pending(session, rid)

        if session.state is TurnState.AWAITING_PIN:
            if audio is not None:  # se descarta sin transcribir ni enviarlo a nadie
                return TurnResult(session, phrases.say(phrases.Situation.PIN_KEYBOARD))
            return self._pin_turn(session, text, rid)

        prefix = self._check_pending_payment(rid)

        voice = NOT_AVAILABLE
        confidence = None
        transcript = text
        if audio is not None:
            is_command = session.state not in (TurnState.AWAITING_CONFIRMATION, TurnState.AWAITING_RECIPIENT_CHOICE)
            transcript, voice, confidence = self._transcribe(audio, rid, verify=is_command)
            if transcript is None:
                return TurnResult(session, prefix + phrases.say(phrases.Situation.NO_SPEECH), transcript="")

        if session.state is TurnState.AWAITING_CONFIRMATION and session.command is not None:
            return self._prefixed(prefix, self._confirmation_turn(session, transcript, rid))
        if session.state is TurnState.AWAITING_RECIPIENT_CHOICE and session.command is not None:
            return self._prefixed(prefix, self._choice_turn(session, transcript, rid))
        return self._prefixed(prefix, self._command_turn(session, transcript, voice, confidence, rid))

    @staticmethod
    def _prefixed(prefix: str, result: TurnResult) -> TurnResult:
        if prefix:
            result.say = prefix + result.say
        return result

    def _transcribe(self, audio, rid, verify):
        from voice.transcribe import TranscribeInputError

        from .voice_io import TranscriptionUnavailable
        try:
            result, voice = self.voice.transcribe_command(audio, rid, verify=verify)
        except TranscribeInputError as err:
            code = err.code.value
            message = "El audio supera los 30 segundos" if code == "AUDIO_TOO_LONG" else "El audio no se pudo leer"
            raise ApiFailure(400, code, message) from None
        except TranscriptionUnavailable:
            raise ApiFailure(500, "INTERNAL_ERROR", "Error interno") from None
        logger.info("transcribed requestId=%s engine=%s speech=%s", rid, result.engine.value, result.had_speech)
        if not result.had_speech or not result.text.strip():
            return None, NOT_AVAILABLE, None
        return result.text.strip(), voice, result.transcript_confidence

    # ----------------------------------------------------------- comando
    def _command_turn(self, session, text, voice, confidence, rid) -> TurnResult:
        auth = self.wallet.pending_auth
        if auth is not None and auth.kind == "excess" and auth.session_id == session.id:
            self._discard_excess(rid)  # comando nuevo: la intención del exceso se descarta
        session.reset_command()
        intent = extract_intent(text, self.asset)
        cmd = Command(intent=intent.to_dict(), voice=voice, transcript_confidence=confidence)
        if intent.recipient is not None:
            cmd.resolution = resolve_recipient(intent.recipient, self.agenda)
        session.command = cmd
        return self._evaluate_command(session, cmd, transcript=text, rid=rid)

    def _evaluate_command(self, session, cmd, transcript, rid) -> TurnResult:
        cmd.quote = None
        cmd.idempotency_key = None
        if self._needs_quote(cmd):
            failure = self._quote(cmd, self.wallet.budget_grant_id, rid)
            if failure is not None:
                return self._quote_failure(session, cmd, failure, transcript)
        ctx = self._context("COMMAND", cmd)
        return self._decide(session, cmd, ctx, transcript, rid)

    def _needs_quote(self, cmd) -> bool:
        intent = cmd.intent
        return (intent["action"] == "PAY" and intent["status"] == "OK" and intent["amount"] is not None
                and intent["amountError"] is None and intent["recipient"] is not None
                and cmd.resolution is not None and cmd.resolution.kind is Kind.RESOLVED
                and self.wallet.budget_grant_id is not None)

    def _quote(self, cmd, grant_id, rid) -> str | None:
        """Pide la quote; devuelve None si salió bien o el `code` de Node si no."""
        contact = cmd.resolution.contact
        try:
            cmd.quote = self.payments.create_quote(grant_id, contact.wallet_address,
                                                   cmd.intent["amount"]["value"], request_id=rid)
        except PaymentsError as err:
            if err.code in ("GRANT_INVALID", "GRANT_NOT_FOUND") and grant_id == self.wallet.budget_grant_id:
                self._forget_budget(grant_id)
            return err.code or "UPSTREAM_ERROR"
        except UpstreamUnavailable:
            raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None
        cmd.quote_grant_id = grant_id
        cmd.idempotency_key = str(uuid.uuid4())  # una clave por quote (intención de pago)
        return None

    def _quote_failure(self, session, cmd, code, transcript) -> TurnResult:
        if code in ("GRANT_INVALID", "GRANT_NOT_FOUND"):
            # El presupuesto ya no sirve: el motor pide autorizar uno nuevo (SEG-1).
            ctx = self._context("COMMAND", cmd)
            return self._decide(session, cmd, ctx, transcript, None)
        session.state = TurnState.AWAITING_COMMAND
        if code in ("INVALID_RECEIVER", "INVALID_WALLET"):
            say = phrases.say(phrases.Situation.NOT_FOUND, spoken=cmd.intent["recipient"] or "")
        elif code == "INVALID_AMOUNT":
            say = phrases.say(phrases.Situation.INVALID_AMOUNT)
        else:
            raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos")
        session.reset_command()
        return TurnResult(session, say, transcript=transcript)

    # ------------------------------------------------- elección de destinatario
    def _choice_turn(self, session, text, rid) -> TurnResult:
        cmd = session.command
        if classify_reply(text) is Reply.NO or extract_intent(text, self.asset).action.value == "CANCEL":
            session.reset_command()
            session.state = TurnState.REJECTED
            return TurnResult(session, phrases.say(phrases.Situation.CANCELLED), transcript=text)
        resolution = resolve_choice(text, session.options, self.agenda)
        if resolution.kind is not Kind.RESOLVED:
            return TurnResult(session, self._choice_say(session.options), transcript=text,
                              options=[o.to_dict() for o in session.options])
        cmd.resolution = resolution
        session.options = ()
        return self._evaluate_command(session, cmd, transcript=text, rid=rid)

    @staticmethod
    def _choice_say(options) -> str:
        if len(options) >= 2:
            return phrases.say(phrases.Situation.CHOICE, names=[o.name for o in options])
        return phrases.say(phrases.Situation.NEAR, name=options[0].name)

    # ------------------------------------------------------------- PIN
    def _pin_turn(self, session, text, rid) -> TurnResult:
        cmd = session.command
        if cmd is None:
            session.state = TurnState.AWAITING_COMMAND
            return TurnResult(session, phrases.say(phrases.Situation.NOT_UNDERSTOOD))
        result = self._verify_pin(text.strip(), session.id)
        pin_ctx = {"result": result.result, "sessionFailures": result.sessionFailures, "locked": result.locked}
        ctx = self._context("PIN", cmd, pin=pin_ctx)
        out = self._decide(session, cmd, ctx, None, rid, pin_remaining=result.remaining)
        out.transcript = None  # B-7: nunca el PIN
        return out

    # ------------------------------------------------------------ confirmación
    def _confirmation_turn(self, session, text, rid) -> TurnResult:
        cmd = session.command
        reply = classify_reply(text)
        ctx = self._context("CONFIRMATION", cmd, reply=reply.value)
        out = self._decide(session, cmd, ctx, text, rid)
        if reply is Reply.UNCLEAR:
            cmd.unclear_replies += 1
        return out

    # ================================================================ motor
    def _context(self, phase, cmd, *, reply=None, pin=None) -> dict:
        resolution = cmd.resolution
        if resolution is None or resolution.kind is Kind.UNCLEAR:
            res = {"kind": "NOT_FOUND"}
        else:
            res = resolution.to_dict()
            if resolution.kind is Kind.RESOLVED:
                contact = res["contact"]
                contact["previouslyPaid"] = contact["previouslyPaid"] or contact["alias"] in self.wallet.paid_aliases
        quote = None
        if cmd.quote is not None:
            quote = {k: cmd.quote[k] for k in ("debitAmount", "receiveAmount", "exceedsRemaining")}
        pending = None
        pp = self.wallet.pending_payment
        if pp is not None:
            pending = {"recipient": pp.receiver, "createdAt": pp.created_at, "status": "PROCESSING"}
        return {
            "phase": phase,
            "intent": cmd.intent,
            "resolution": res,
            "voice": {"status": cmd.voice["status"], "score": cmd.voice.get("score")},
            "enrolled": self.voice.enrolled(),
            "hasBudgetGrant": self.wallet.budget_grant_id is not None,
            "quote": quote,
            "pendingPayment": pending,
            "now": _iso(self._clock()),
            "reply": reply,
            "unclearReplies": cmd.unclear_replies,
            "pin": pin or {"result": None, "sessionFailures": 0, "locked": False},
            "transcriptConfidence": cmd.transcript_confidence,
            "intentConfidence": None,
            "config": {
                "highAmountThreshold": self.settings.high_amount_threshold,
                "pendingWindowSeconds": self.settings.pending_window_seconds,
                "minIntentConfidence": None,
                "minTranscriptConfidence": None,
            },
        }

    def _decide(self, session, cmd, ctx_dict, transcript, rid, pin_remaining=None) -> TurnResult:
        try:
            context = parse_context(ctx_dict)
            decision = decide(context)
            situation = say_situation(decision, context)
        except InvalidContextError:
            logger.error("Invalid engine context requestId=%s phase=%s", rid, ctx_dict.get("phase"))
            raise ApiFailure(500, "INTERNAL_ERROR", "Error interno") from None
        logger.info("decision requestId=%s phase=%s decision=%s reason=%s", rid, ctx_dict["phase"],
                    decision.decision.value, decision.reason.value)
        say = self._say(situation, cmd, pin_remaining) if situation else ""
        kind = decision.decision

        if kind is DecisionType.REASK:
            session.state = TurnState.AWAITING_COMMAND
            session.reset_command()
            return TurnResult(session, say, transcript=transcript)
        if kind is DecisionType.ASK_RECIPIENT:
            session.state = TurnState.AWAITING_RECIPIENT_CHOICE
            session.options = cmd.resolution.options
            return TurnResult(session, say, transcript=transcript, options=[o.to_dict() for o in session.options])
        if kind is DecisionType.ASK_PIN:
            session.state = TurnState.AWAITING_PIN
            return TurnResult(session, say, transcript=transcript)
        if kind is DecisionType.ASK_CONFIRM:
            if decision.reason is Reason.PIN_CORRECT:
                cmd.pin_ok = True
            session.state = TurnState.AWAITING_CONFIRMATION
            return TurnResult(session, say, transcript=transcript)
        if kind is DecisionType.REQUIRE_AUTH:
            if decision.reason is Reason.NO_BUDGET_GRANT:
                return self._start_budget_auth(session, say, transcript, rid)
            return self._start_excess_auth(session, cmd, say, transcript, rid)
        if kind is DecisionType.PAY:
            out = self._pay(session, cmd, rid)
            out.transcript = transcript
            return out
        # REJECT
        session.state = TurnState.REJECTED
        session.reset_command()
        self._discard_excess(rid)
        return TurnResult(session, say, transcript=transcript)

    def _say(self, situation: str, cmd, pin_remaining) -> str:
        name = situation
        sit = phrases.Situation(name)
        contact = cmd.resolution.contact if cmd.resolution is not None and cmd.resolution.kind is Kind.RESOLVED else None
        available = {
            "spoken": cmd.intent.get("recipient") or "",
            "scale": self.settings.asset_scale,
            "remaining": pin_remaining,
        }
        if contact is not None:
            available["name"] = contact.name
        if cmd.resolution is not None and cmd.resolution.options:
            available["names"] = [o.name for o in cmd.resolution.options]
            available.setdefault("name", cmd.resolution.options[0].name)
        if cmd.quote is not None:
            available["amount"] = _vamount(cmd.quote["receiveAmount"])
        elif cmd.intent.get("amount"):
            available["amount"] = _vamount(cmd.intent["amount"])
        required = phrases.REQUIRED.get(sit, set())
        return phrases.say(sit, **{k: available[k] for k in required})

    # ================================================================ pagos
    def _pay(self, session, cmd, rid) -> TurnResult:
        quote = cmd.quote
        contact = cmd.resolution.contact
        for attempt in range(2):
            try:
                result = self.payments.create_payment(quote["quoteId"], cmd.idempotency_key, request_id=rid)
                break
            except PaymentsError as err:
                if err.code == "LIMIT_EXCEEDED":
                    return self._start_excess_auth(session, cmd, phrases.say(phrases.Situation.AUTH_REDIRECT), None, rid)
                if err.code == "GRANT_INVALID":
                    if cmd.quote_grant_id == self.wallet.budget_grant_id:
                        self._forget_budget(cmd.quote_grant_id)
                        return self._start_budget_auth(session, phrases.say(phrases.Situation.AUTH_BUDGET), None, rid)
                    return self._start_excess_auth(session, cmd, phrases.say(phrases.Situation.AUTH_REDIRECT), None, rid)
                if err.code == "QUOTE_EXPIRED" and attempt == 0:
                    failure = self._quote(cmd, cmd.quote_grant_id, rid)  # recotiza: clave nueva
                    if failure is not None:
                        return self._payment_failed(session)
                    quote = cmd.quote
                    if quote["exceedsRemaining"]:
                        return self._start_excess_auth(session, cmd, phrases.say(phrases.Situation.AUTH_OVERRUN), None, rid)
                    continue
                logger.warning("Payment rejected by Node requestId=%s code=%s", rid, err.code)
                return self._payment_failed(session)
            except UpstreamUnavailable:
                result = PaymentPending(payment_id=None)
                break

        pending = PendingPayment(session.id, None, quote["quoteId"], cmd.idempotency_key, contact.wallet_address,
                                 contact.name, quote["receiveAmount"], quote["debitAmount"], _iso(self._clock()),
                                 cmd.quote_grant_id if cmd.quote_grant_id != self.wallet.budget_grant_id else None,
                                 contact.alias)
        if isinstance(result, PaymentPending):
            return self._payment_pending(session, pending)
        pending.payment_id = result["paymentId"]
        if result.get("status") == "PROCESSING":
            try:
                result = self.payments.wait_for_payment(pending.payment_id, request_id=rid)
            except (PaymentsError, UpstreamUnavailable):
                result = PaymentPending(payment_id=pending.payment_id)
            if isinstance(result, PaymentPending):
                return self._payment_pending(session, pending)
        return self._payment_outcome(session, pending, result, rid)

    def _payment_outcome(self, session, pending: PendingPayment, payment: dict, rid) -> TurnResult:
        if self.wallet.pending_payment is pending or (
                self.wallet.pending_payment and self.wallet.pending_payment.quote_id == pending.quote_id):
            self.wallet.pending_payment = None
        if pending.one_off_grant_id:
            self._cancel_grant(pending.one_off_grant_id, rid)  # el puntual no queda ACTIVE
        if payment.get("status") == "FAILED":
            return self._payment_failed(session)
        alias = pending.alias
        if alias:
            self.wallet.paid_aliases.add(alias)
            self.wallet.save()
        receive = pending.receive_amount
        debit = payment.get("debitAmount") or pending.debit_amount
        params = {"amount": _vamount(receive), "name": pending.contact_name}
        if (debit["assetCode"], debit["assetScale"]) == (receive["assetCode"], receive["assetScale"]) \
                and int(debit["value"]) >= int(receive["value"]):
            params["debit"] = _vamount(debit)
        session.state = TurnState.COMPLETED
        session.reset_command()
        return TurnResult(session, phrases.say(phrases.Situation.COMPLETED, **params),
                          payment=self._payment_body(pending, debit))

    def _payment_pending(self, session, pending: PendingPayment) -> TurnResult:
        self.wallet.pending_payment = pending
        session.state = TurnState.PAYMENT_PENDING
        session.reset_command()
        body = self._payment_body(pending, pending.debit_amount) if pending.payment_id else None
        return TurnResult(session, phrases.say(phrases.Situation.PAYMENT_PENDING), payment=body)

    def _payment_failed(self, session) -> TurnResult:
        session.state = TurnState.REJECTED
        session.reset_command()
        return TurnResult(session, FALLBACK_SAY["PAYMENT_FAILED"])

    @staticmethod
    def _payment_body(pending: PendingPayment, debit: dict) -> dict:
        return {"paymentId": pending.payment_id, "receiver": pending.receiver,
                "debitAmount": debit, "receiveAmount": pending.receive_amount}

    def _resolve_pending(self, rid):
        """Consulta (o reintenta con la misma clave) el pago pendiente. Devuelve el dict del pago
        final, o None si sigue en proceso."""
        pp = self.wallet.pending_payment
        if pp.payment_id is None:
            result = self.payments.create_payment(pp.quote_id, pp.idempotency_key, request_id=rid)
            if isinstance(result, PaymentPending):
                return None
            pp.payment_id = result["paymentId"]
            if result.get("status") in ("COMPLETED", "FAILED"):
                return result
        payment = self.payments.get_payment(pp.payment_id, request_id=rid)
        return payment if payment.get("status") in ("COMPLETED", "FAILED") else None

    def _verify_pending(self, session, rid) -> TurnResult:
        pp = self.wallet.pending_payment
        if pp is None:  # ya se resolvió en otro turno (o nunca hubo pago pendiente)
            was_pending = session.state is TurnState.PAYMENT_PENDING
            session.state = TurnState.AWAITING_COMMAND
            return TurnResult(session, FALLBACK_SAY["PENDING_COMPLETED"] if was_pending
                              else phrases.say(phrases.Situation.NOT_UNDERSTOOD))
        try:
            payment = self._resolve_pending(rid)
        except PaymentsError as err:
            if err.code in ("QUOTE_NOT_FOUND", "QUOTE_EXPIRED", "IDEMPOTENCY_KEY_REUSED"):
                self.wallet.pending_payment = None
                return self._payment_failed(session)
            payment = None
        except UpstreamUnavailable:
            payment = None
        if payment is None:
            session.state = TurnState.PAYMENT_PENDING
            body = self._payment_body(pp, pp.debit_amount) if pp.payment_id else None
            return TurnResult(session, phrases.say(phrases.Situation.PAYMENT_PENDING), payment=body)
        return self._payment_outcome(session, pp, payment, rid)

    def _check_pending_payment(self, rid) -> str:
        """Antes de un turno nuevo: si el pago pendiente ya se resolvió, se informa y se sigue."""
        pp = self.wallet.pending_payment
        if pp is None:
            return ""
        try:
            payment = self._resolve_pending(rid)
        except (PaymentsError, UpstreamUnavailable):
            return ""
        if payment is None:
            return ""
        self.wallet.pending_payment = None
        if pp.one_off_grant_id:
            self._cancel_grant(pp.one_off_grant_id, rid)
        if payment.get("status") == "FAILED":
            return FALLBACK_SAY["PAYMENT_FAILED"] + " "
        alias = pp.alias
        if alias:
            self.wallet.paid_aliases.add(alias)
            self.wallet.save()
        return FALLBACK_SAY["PENDING_COMPLETED"] + " "

    # ============================================================ autorización
    def _create_grant(self, debit_value: str, interval: str | None, rid) -> dict:
        if not self.settings.wallet_address:
            logger.error("EZPAY_WALLET_ADDRESS is not configured")
            raise ApiFailure(500, "INTERNAL_ERROR", "Error interno")
        try:
            return self.payments.create_grant(self.settings.user_id, self.settings.wallet_address,
                                              self.settings.finish_uri, debit_value, interval, request_id=rid)
        except PaymentsError as err:
            if err.code == "INVALID_AMOUNT":
                raise ApiFailure(400, "INVALID_AMOUNT", "El monto no es válido") from None
            raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None
        except UpstreamUnavailable:
            raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None

    def _start_budget_auth(self, session, say, transcript, rid) -> TurnResult:
        grant = self._create_grant(self.settings.default_budget_value, self.settings.default_budget_interval, rid)
        self._replace_pending_auth(PendingAuth("budget", grant["grantId"], session.id), rid)
        session.state = TurnState.AWAITING_AUTHORIZATION
        return TurnResult(session, say, transcript=transcript, interact_url=grant["interactUrl"])

    def _start_excess_auth(self, session, cmd, say, transcript, rid) -> TurnResult:
        debit = cmd.quote["debitAmount"]["value"]
        grant = self._create_grant(debit, one_off_interval(self._clock()), rid)
        self._replace_pending_auth(PendingAuth("excess", grant["grantId"], session.id), rid)
        session.state = TurnState.AWAITING_AUTHORIZATION
        return TurnResult(session, say, transcript=transcript, interact_url=grant["interactUrl"])

    def _replace_pending_auth(self, auth: PendingAuth, rid) -> None:
        self._discard_excess(rid)
        self.wallet.pending_auth = auth

    def _discard_excess(self, rid) -> None:
        """Cancela el grant puntual que esperaba aprobación (intención descartada o reemplazada)."""
        old = self.wallet.pending_auth
        if old is not None and old.kind == "excess":
            self._cancel_grant(old.grant_id, rid)
        self.wallet.pending_auth = None

    def _cancel_grant(self, grant_id, rid) -> None:
        try:
            self.payments.cancel_grant(grant_id, request_id=rid)
        except (PaymentsError, UpstreamUnavailable) as err:
            logger.warning("One-off grant cancel failed requestId=%s (%s)", rid, type(err).__name__)

    def _forget_budget(self, grant_id) -> None:
        if self.wallet.budget_grant_id == grant_id:
            self.wallet.budget_grant_id = None
            self.wallet.save()

    def _grant_callback(self, body: dict, rid) -> TurnResult:
        auth = self.wallet.pending_auth
        session = self.sessions.get(auth.session_id) if auth and auth.session_id else None
        session = session or self.sessions.create()
        interact_ref, hash_value = body.get("interactRef"), body.get("hash")
        if auth is None or not interact_ref or not hash_value:
            # Rechazo en la wallet (B-1) o callback sin autorización en curso (D-2 de Pagos):
            # no se llama a /continue y la intención se descarta.
            self.wallet.pending_auth = None
            if auth is not None and auth.kind == "excess":
                self._cancel_grant(auth.grant_id, rid)
            session.state = TurnState.REJECTED
            session.reset_command()
            return TurnResult(session, phrases.say(phrases.Situation.AUTH_REJECTED))
        try:
            grant = self.payments.continue_grant(auth.grant_id, interact_ref, hash_value, request_id=rid)
        except PaymentsError as err:
            logger.warning("Grant continue failed requestId=%s code=%s", rid, err.code)
            self.wallet.pending_auth = None
            session.state = TurnState.REJECTED
            session.reset_command()
            return TurnResult(session, phrases.say(phrases.Situation.AUTH_REJECTED))
        except UpstreamUnavailable:
            raise ApiFailure(502, "UPSTREAM_ERROR", "No se pudo contactar al servicio de pagos") from None
        self.wallet.pending_auth = None
        if grant.get("status") != "ACTIVE":
            session.state = TurnState.REJECTED
            session.reset_command()
            return TurnResult(session, phrases.say(phrases.Situation.AUTH_REJECTED))

        if auth.kind == "budget":
            self.wallet.budget_grant_id = auth.grant_id
            self.wallet.save()
            cmd = session.command
            if cmd is not None and session.state is TurnState.AWAITING_AUTHORIZATION:
                return self._evaluate_command(session, cmd, transcript=None, rid=rid)  # retoma el comando
            session.state = TurnState.AWAITING_COMMAND
            session.reset_command()
            return TurnResult(session, FALLBACK_SAY["BUDGET_APPROVED"])

        # Grant puntual del exceso: recotiza con el puntual y paga con clave nueva si entra.
        cmd = session.command
        if cmd is None:
            self._cancel_grant(auth.grant_id, rid)
            session.state = TurnState.AWAITING_COMMAND
            return TurnResult(session, phrases.say(phrases.Situation.AUTH_APPROVED))
        failure = self._quote(cmd, auth.grant_id, rid)
        if failure is not None:
            self._cancel_grant(auth.grant_id, rid)
            return self._payment_failed(session)
        if cmd.quote["exceedsRemaining"]:
            self._cancel_grant(auth.grant_id, rid)
            return self._start_excess_auth(session, cmd, FALLBACK_SAY["DEBIT_CHANGED"], None, rid)
        return self._pay(session, cmd, rid)

    def _check_amount(self, amount) -> None:
        ok = (isinstance(amount, dict) and isinstance(amount.get("value"), str)
              and re.fullmatch(r"[0-9]+", amount["value"]) is not None and int(amount["value"]) > 0
              and amount.get("assetCode") == self.settings.asset_code
              and amount.get("assetScale") == self.settings.asset_scale)
        if not ok:
            raise ApiFailure(400, "INVALID_AMOUNT", "El monto no es válido")
