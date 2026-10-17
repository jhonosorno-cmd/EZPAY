"""`decision/say_map.py`: Decision + Context -> situación del catálogo de Voz (solo el NOMBRE).

Los textos viven SOLO en `voice/phrases.py` (catálogo de Voz, PR #4); el motor no tiene textos.
El orquestador llama `voice.phrases.say(Situation(nombre), **params)`.
"""
import unittest

from decision import InvalidContextError
from decision.models import Confirmation, Decision, DecisionType, Reason
from decision.say_map import (PENDING_VOZ_SITUATIONS, VOICE_SITUATIONS_EXISTING,
                              VOICE_SITUATIONS_NEW, say_situation)
import decision_fixtures as f


def verified(**overrides):
    base = {"voice": f.Voice(status="VERIFIED", score=0.9), "enrolled": True}
    base.update(overrides)
    return f.command_context(**base)


def pending_past(quote=None):
    values = {
        "voice": f.Voice(status="VERIFIED", score=0.9),
        "enrolled": True,
        "pendingPayment": f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
        "quote": quote or f.QUOTE_WITHIN_BUDGET,
    }
    return f.command_context(**values)


# (Reason, situación esperada o None, context)
PAIRS = [
    (Reason.CANCELLED_BY_USER, "CANCELLED", f.command_context(intent=f.intent(action="CANCEL"))),
    (Reason.INTENT_UNKNOWN, "NOT_UNDERSTOOD", f.command_context(intent=f.intent(action="UNKNOWN"))),
    (Reason.INTENT_UNCLEAR, "NOT_UNDERSTOOD", f.command_context(intent=f.intent(status="UNCLEAR"))),
    (Reason.AMOUNT_MISSING, "AMOUNT_MISSING", f.command_context(intent=f.intent(amount=None, status="UNCLEAR"))),
    (Reason.RECIPIENT_MISSING, "RECIPIENT_MISSING", f.command_context(intent=f.intent(recipient=None, status="UNCLEAR"))),
    (Reason.AMOUNT_ERROR, "TOO_MANY_DECIMALS", f.command_context(intent=f.intent(amountError="TOO_MANY_DECIMALS"))),
    (Reason.AMOUNT_ERROR, "AMOUNT_AMBIGUOUS", f.command_context(intent=f.intent(amountError="AMBIGUOUS_AMOUNT"))),
    (Reason.AMOUNT_ERROR, "INVALID_AMOUNT", f.command_context(intent=f.intent(amountError="INVALID_AMOUNT"))),
    (Reason.RECIPIENT_NOT_FOUND, "NOT_FOUND", f.command_context(resolution=f.Resolution(kind="NOT_FOUND"))),
    (Reason.RECIPIENT_AMBIGUOUS, "CHOICE", f.command_context(resolution=f.resolution_choice("Laura hija", "Laura vecina"))),
    (Reason.RECIPIENT_AMBIGUOUS, "NEAR", f.command_context(resolution=f.resolution_choice("Laura hija"))),
    (Reason.NO_BUDGET_GRANT, "AUTH_BUDGET", f.command_context(hasBudgetGrant=False, quote=None)),
    (Reason.VOICE_NOT_VERIFIED, "PIN_KEYBOARD", f.command_context()),
    (Reason.ALL_CHECKS_PASSED, "CONFIRM", verified()),
    (Reason.ALL_CHECKS_PASSED, "AUTH_OVERRUN", verified(quote=f.QUOTE_EXCEEDS_BUDGET)),
    (Reason.PIN_CORRECT, "CONFIRM", f.pin_context()),
    (Reason.PIN_CORRECT, "AUTH_OVERRUN", f.pin_context(quote=f.QUOTE_EXCEEDS_BUDGET)),
    (Reason.PENDING_PAYMENT_UNCONFIRMED, "PENDING_PAYMENT_UNCONFIRMED", pending_past()),
    (Reason.PENDING_PAYMENT_UNCONFIRMED, "PENDING_PAYMENT_UNCONFIRMED_OVERRUN", pending_past(quote=f.QUOTE_EXCEEDS_BUDGET)),
    (Reason.CONFIRMED, None, f.confirmation_context(reply="YES")),
    (Reason.CONFIRMED_NEEDS_WALLET_AUTH, "AUTH_REDIRECT", f.confirmation_context(reply="YES", quote=f.QUOTE_EXCEEDS_BUDGET)),
    (Reason.USER_DECLINED, "CANCELLED", f.confirmation_context(reply="NO")),
    (Reason.REPLY_UNCLEAR_ASK_AGAIN, "CONFIRM_UNCLEAR", f.confirmation_context(reply="UNCLEAR", unclearReplies=0)),
    (Reason.REPLY_UNCLEAR_REJECTED, "REPLY_UNCLEAR_REJECTED", f.confirmation_context(reply="UNCLEAR", unclearReplies=1)),
    (Reason.INTENT_AMBIGUOUS, "INTENT_AMBIGUOUS", f.command_context(intent=f.intent(status="AMBIGUOUS", amount=None))),
    (Reason.INTENT_LOW_CONFIDENCE, "INTENT_LOW_CONFIDENCE", f.command_context(config=f.config(minIntentConfidence=0.7), intentConfidence=0.4)),
    (Reason.TRANSCRIPT_LOW_CONFIDENCE, "TRANSCRIPT_LOW_CONFIDENCE", f.command_context(config=f.config(minIntentConfidence=0.7, minTranscriptConfidence=0.5), intentConfidence=0.7, transcriptConfidence=0.2)),
    (Reason.PENDING_PAYMENT_SAME_RECIPIENT, "PENDING_PAYMENT_SAME_RECIPIENT", f.command_context(pendingPayment=f.pending_payment())),
    (Reason.NEW_RECIPIENT, "NEW_RECIPIENT", verified(resolution=f.resolution_resolved(f.LUCIA))),
    (Reason.HIGH_AMOUNT, "HIGH_AMOUNT", verified(quote=f.Quote(f.Amount("6015000", "COP", 2), f.Amount("6000000", "COP", 2), False), config=f.config(highAmountThreshold=f.FIFTY_THOUSAND_COP))),
    (Reason.PIN_WRONG, "PIN_WRONG", f.pin_context(pin=f.PinContext(result="WRONG", sessionFailures=1, locked=False))),
    (Reason.PIN_ATTEMPTS_EXHAUSTED, "PIN_ATTEMPTS_EXHAUSTED", f.pin_context(pin=f.PinContext(result="WRONG", sessionFailures=3, locked=False))),
    (Reason.PIN_LOCKED, "PIN_LOCKED", f.pin_context(pin=f.PinContext(result=None, sessionFailures=0, locked=True))),
    (Reason.PIN_INVALID_FORMAT, "PIN_INVALID_FORMAT", f.pin_context(pin=f.PinContext(result="INVALID_FORMAT", sessionFailures=0, locked=False))),
    # B11: desafío de voz (el motor emite estos reasons con confirmation.mode == CHALLENGE)
    (Reason.CHALLENGE_RETRY, "CHALLENGE_RETRY", f.confirmation_context(confirmation=Confirmation(mode="CHALLENGE", phrase_score=0.1, voice=None, challenge_attempts=0))),
    (Reason.CHALLENGE_FAILED, "CHALLENGE_FAILED", f.confirmation_context(confirmation=Confirmation(mode="CHALLENGE", phrase_score=0.1, voice=None, challenge_attempts=1))),
    (Reason.CHALLENGE_VOICE_NOT_VERIFIED, "PIN_KEYBOARD", f.confirmation_context(confirmation=Confirmation(mode="CHALLENGE", phrase_score=0.95, voice=None, challenge_attempts=0))),
    (Reason.CONFIRMED_WITH_PIN, None, f.pin_context(confirmation=Confirmation(mode="CHALLENGE", phrase_score=0.95, voice=None, challenge_attempts=1))),
]


class CadaReasonTieneTraduccion(unittest.TestCase):
    def test_todas_las_variantes_de_la_tabla(self):
        for reason, expected, context in PAIRS:
            result = say_situation(Decision(DecisionType.REASK, reason), context)
            self.assertEqual(result, expected, reason)


class TodoReasonDelEnumEstaCubierto(unittest.TestCase):
    def test_32_reasons_en_la_tabla(self):
        covered = {reason for reason, _, _ in PAIRS}
        self.assertEqual(covered, set(Reason))


class SituacionesDevueltas(unittest.TestCase):
    def test_toda_situacion_esta_en_existing_union_new(self):
        allowed = set(VOICE_SITUATIONS_EXISTING) | set(VOICE_SITUATIONS_NEW)
        for reason, _, context in PAIRS:
            result = say_situation(Decision(DecisionType.REASK, reason), context)
            if result is None:
                # B11: CONFIRMED_WITH_PIN tampoco tiene situación (el say sale del pago)
                self.assertIn(reason, (Reason.CONFIRMED, Reason.CONFIRMED_WITH_PIN))
            else:
                self.assertIn(result, allowed, reason)

    def test_confirmed_devuelve_none(self):
        self.assertIsNone(say_situation(Decision(DecisionType.PAY, Reason.CONFIRMED), f.confirmation_context(reply="YES")))

    def test_determinismo(self):
        for reason, _, context in PAIRS:
            first = say_situation(Decision(DecisionType.REASK, reason), context)
            second = say_situation(Decision(DecisionType.REASK, reason), context)
            self.assertEqual(first, second, reason)

    def test_resultado_sin_datos_del_request(self):
        for reason, _, context in PAIRS:
            result = say_situation(Decision(DecisionType.REASK, reason), context)
            if result is not None:
                self.assertRegex(result, r"^[A-Z_]+$", reason)


class Catalogos(unittest.TestCase):
    def test_existing_tiene_21_y_new_tiene_17(self):
        self.assertEqual(len(set(VOICE_SITUATIONS_EXISTING)), 21)
        self.assertEqual(len(set(VOICE_SITUATIONS_NEW)), 17)  # 13 + las 4 del desafío (B11)
        self.assertEqual(set(VOICE_SITUATIONS_EXISTING) & set(VOICE_SITUATIONS_NEW), set())

    def test_new_lleva_los_once_con_el_mismo_nombre_del_reason(self):
        same_name = {
            "INTENT_AMBIGUOUS", "INTENT_LOW_CONFIDENCE", "TRANSCRIPT_LOW_CONFIDENCE",
            "PENDING_PAYMENT_SAME_RECIPIENT", "NEW_RECIPIENT", "HIGH_AMOUNT", "PIN_WRONG",
            "PIN_ATTEMPTS_EXHAUSTED", "PIN_LOCKED", "PIN_INVALID_FORMAT", "REPLY_UNCLEAR_REJECTED",
        }
        self.assertEqual(same_name, set(Reason.__members__) & same_name)
        self.assertTrue(same_name.issubset(set(VOICE_SITUATIONS_NEW)))

    def test_voz_ya_agrego_las_del_desafio_y_no_quedan_pendientes(self):
        self.assertEqual(PENDING_VOZ_SITUATIONS, frozenset())
        self.assertTrue({"CONFIRM_CHALLENGE_OVERRUN", "CHALLENGE_FAILED"}.issubset(set(VOICE_SITUATIONS_NEW)))


class ContextosInvalidos(unittest.TestCase):
    def test_amount_error_sin_amount_error(self):
        with self.assertRaises(InvalidContextError):
            say_situation(Decision(DecisionType.REASK, Reason.AMOUNT_ERROR), f.command_context())

    def test_variantes_de_confirmacion_sin_quote(self):
        for reason in (Reason.ALL_CHECKS_PASSED, Reason.PIN_CORRECT, Reason.PENDING_PAYMENT_UNCONFIRMED):
            with self.assertRaises(InvalidContextError):
                say_situation(Decision(DecisionType.ASK_CONFIRM, reason), f.pin_context(quote=None))

    def test_choice_sin_opciones(self):
        empty_choice = f.Resolution(kind="CHOICE", options=())
        with self.assertRaises(InvalidContextError):
            say_situation(Decision(DecisionType.ASK_RECIPIENT, Reason.RECIPIENT_AMBIGUOUS), f.command_context(resolution=empty_choice))


class IntegracionConElCatalogoDeVoz(unittest.TestCase):
    def test_las_situaciones_existentes_yan_estan_en_voice_phrases(self):
        try:
            from voice import phrases
        except ImportError:
            self.skipTest("voice/phrases.py no está en esta rama todavía")
        names = {situation.value for situation in phrases.Situation}
        missing_existing = [name for name in VOICE_SITUATIONS_EXISTING if name not in names]
        self.assertEqual(missing_existing, [])
        missing_new = [name for name in VOICE_SITUATIONS_NEW if name not in names]
        if missing_new:
            print(f"Situaciones NEW aún no en voice.phrases.Situation: {missing_new}")

    def test_si_voz_agrega_una_situacion_pendiente_hay_que_quitarla_del_set(self):
        try:
            from voice import phrases
        except ImportError:
            self.skipTest("voice/phrases.py no está en esta rama todavía")
        nombres = {situation.value for situation in phrases.Situation}
        self.assertEqual(
            PENDING_VOZ_SITUATIONS & nombres, set(),
            "Voz ya tiene esas situaciones: quítalas de PENDING_VOZ_SITUATIONS en say_map.py")