"""B11 — Confirmación con desafío de voz (spec: "Confirmación con desafío de
voz", "Tabla de la fase PIN", "El motor no obedece al LLM").

Supuesto: `phraseScore` es un número dado por Voz (la coincidencia de texto la
prueba Voz con `phrase_match` por su lado; aquí NO se implementa). El modo lo
decide el orquestador: el motor solo lee `confirmation.mode` (SEG-3).
"""
import math
import unittest

from decision import InvalidContextError
from decision.context_io import decide_dict, parse_context
from decision.engine import decide
from decision.models import (
    Confirmation,
    Decision,
    DecisionType,
    PinContext,
    Reason,
    Voice,
)
from decision.say_map import PENDING_VOZ_SITUATIONS, VOICE_SITUATIONS_NEW, say_situation
import decision_fixtures as f


def challenge_confirmation(phrase_score=1.0, voice_status="VERIFIED", attempts=0, mode="CHALLENGE"):
    voice = None if voice_status is None else Voice(status=voice_status, score=None)
    return Confirmation(mode=mode, phrase_score=phrase_score, voice=voice, challenge_attempts=attempts)


def ctx_desafio(phrase_score=1.0, voice_status="VERIFIED", attempts=0, reply=None,
                quote=None, mode="CHALLENGE", **overrides):
    base = {
        "confirmation": challenge_confirmation(phrase_score, voice_status, attempts, mode),
        "reply": reply,
        "quote": quote if quote is not None else f.QUOTE_WITHIN_BUDGET,
    }
    base.update(overrides)
    return f.confirmation_context(**base)


def ctx_pin_desafio(pin_result="OK", sessionFailures=0, locked=False, phrase_score=1.0,
                    attempts=1, quote=None, mode="CHALLENGE"):
    return f.pin_context(
        pin=PinContext(result=pin_result, sessionFailures=sessionFailures, locked=locked),
        quote=quote if quote is not None else f.QUOTE_WITHIN_BUDGET,
        confirmation=challenge_confirmation(phrase_score, voice_status=None, attempts=attempts, mode=mode),
    )


def decide_pair(context):
    decision = decide(context)
    return (decision.decision.value, decision.reason.value)


class DesafioCorrecto(unittest.TestCase):
    def test_frase_que_coincide_y_voz_verificada_paga(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=1.0)),
                         ("PAY", "CONFIRMED"))

    def test_con_exceso_de_presupuesto_pide_autorizacion(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=1.0, quote=f.QUOTE_EXCEEDS_BUDGET)),
                         ("REQUIRE_AUTH", "CONFIRMED_NEEDS_WALLET_AUTH"))

    def test_en_el_borde_0_80_cuenta_como_coincidente(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.80)), ("PAY", "CONFIRMED"))

    def test_0_7999_no_coincide_y_pide_otra_frase(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.7999, attempts=0)),
                         ("ASK_CONFIRM", "CHALLENGE_RETRY"))

    def test_el_corte_es_configurable_y_el_borde_inclusivo(self):
        ctx = ctx_desafio(phrase_score=0.9, config=f.config(challenge_phrase_match_min=0.9))
        self.assertEqual(decide_pair(ctx), ("PAY", "CONFIRMED"))


class FraseCorrectaYVozNoVerificada(unittest.TestCase):
    def test_con_voz_de_otra_persona_pide_pin(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.95, voice_status="BELOW_THRESHOLD")),
                         ("ASK_PIN", "CHALLENGE_VOICE_NOT_VERIFIED"))

    def test_con_voz_no_disponible_pide_pin(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.95, voice_status="NOT_AVAILABLE")),
                         ("ASK_PIN", "CHALLENGE_VOICE_NOT_VERIFIED"))

    def test_sin_voz_en_la_confirmacion_pide_pin(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.95, voice_status=None)),
                         ("ASK_PIN", "CHALLENGE_VOICE_NOT_VERIFIED"))

    def test_los_tres_caminos_no_importan_la_voz_del_contexto_del_comando(self):
        # el motor mira confirmation.voice, no context.voice (D4: el motor no verifica)
        ctx = ctx_desafio(phrase_score=0.95, voice_status="VERIFIED",
                          voice=f.Voice(status="BELOW_THRESHOLD", score=0.1))
        self.assertEqual(decide_pair(ctx), ("PAY", "CONFIRMED"))


class FraseIncorrecta(unittest.TestCase):
    def test_primera_vez_pide_otra_frase(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.1, attempts=0)),
                         ("ASK_CONFIRM", "CHALLENGE_RETRY"))

    def test_segunda_vez_rechaza(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.1, attempts=1)),
                         ("REJECT", "CHALLENGE_FAILED"))

    def test_quinta_vez_rechaza(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=0.1, attempts=5)),
                         ("REJECT", "CHALLENGE_FAILED"))

    def test_phrase_score_none_se_trata_como_no_coincidente(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=None, attempts=0)),
                         ("ASK_CONFIRM", "CHALLENGE_RETRY"))
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=None, attempts=1)),
                         ("REJECT", "CHALLENGE_FAILED"))

    def test_grabacion_reproducida_retry_y_luego_reject(self):
        grabacion = {"phrase_score": 0.2, "attempts": 0}
        primera = decide_pair(ctx_desafio(phrase_score=grabacion["phrase_score"], attempts=grabacion["attempts"]))
        self.assertEqual(primera, ("ASK_CONFIRM", "CHALLENGE_RETRY"))
        segunda = decide_pair(ctx_desafio(phrase_score=grabacion["phrase_score"], attempts=1))
        self.assertEqual(segunda, ("REJECT", "CHALLENGE_FAILED"))


class NoGanaAunqueLaFraseCoincida(unittest.TestCase):
    def test_el_no_va_antes_de_evaluar_la_frase(self):
        self.assertEqual(decide_pair(ctx_desafio(phrase_score=1.0, reply="NO")),
                         ("REJECT", "USER_DECLINED"))


class ModoReplyYConfirmationNulaQuedanComoHoy(unittest.TestCase):
    def test_reply_con_confirmation_reply(self):
        self.assertEqual(decide_pair(ctx_desafio(reply="YES", mode="REPLY")), ("PAY", "CONFIRMED"))
        self.assertEqual(decide_pair(ctx_desafio(reply="NO", mode="REPLY")), ("REJECT", "USER_DECLINED"))
        self.assertEqual(decide_pair(ctx_desafio(reply=None, mode="REPLY", attempts=0)),
                         ("ASK_CONFIRM", "REPLY_UNCLEAR_ASK_AGAIN"))

    def test_confirmation_none_comportamiento_actual(self):
        self.assertEqual(decide_pair(f.confirmation_context(reply="YES")), ("PAY", "CONFIRMED"))
        self.assertEqual(decide_pair(f.confirmation_context(reply="NO")), ("REJECT", "USER_DECLINED"))


class PinTrasElDesafio(unittest.TestCase):
    def test_pin_ok_con_frase_coincidente_paga(self):
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="OK", phrase_score=1.0)),
                         ("PAY", "CONFIRMED_WITH_PIN"))

    def test_pin_ok_con_exceso_pide_autorizacion(self):
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="OK", quote=f.QUOTE_EXCEEDS_BUDGET)),
                         ("REQUIRE_AUTH", "CONFIRMED_NEEDS_WALLET_AUTH"))

    def test_pin_ok_con_frase_que_no_coincide_comportamiento_actual(self):
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="OK", phrase_score=0.1)),
                         ("ASK_CONFIRM", "PIN_CORRECT"))
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="OK", phrase_score=None)),
                         ("ASK_CONFIRM", "PIN_CORRECT"))

    def test_el_bloqueo_sigue_ganando_primero(self):
        self.assertEqual(decide_pair(ctx_pin_desafio(locked=True, phrase_score=1.0)),
                         ("REJECT", "PIN_LOCKED"))

    def test_wrong_exhausted_e_invalid_format_sin_cambios(self):
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="WRONG", sessionFailures=1)),
                         ("ASK_PIN", "PIN_WRONG"))
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="WRONG", sessionFailures=3)),
                         ("REJECT", "PIN_ATTEMPTS_EXHAUSTED"))
        self.assertEqual(decide_pair(ctx_pin_desafio(pin_result="INVALID_FORMAT")),
                         ("ASK_PIN", "PIN_INVALID_FORMAT"))


class InvarianteSeg3SoloHayTresCaminosAPay(unittest.TestCase):
    PHRASES = (None, 0.0, 0.79, 0.80, 1.0)
    VOICES = (None, "VERIFIED", "BELOW_THRESHOLD", "NOT_AVAILABLE")
    PINS = (None, "OK", "WRONG", "INVALID_FORMAT")
    MODES = (None, "REPLY", "CHALLENGE")
    REPLIES = (None, "YES", "NO", "UNCLEAR")

    def _context(self, phase, mode, reply, phrase, voice_status, pin_result, attempts, locked):
        confirmation = None if mode is None else challenge_confirmation(
            phrase_score=phrase, voice_status=voice_status, attempts=attempts, mode=mode)
        if phase == "COMMAND":
            return f.command_context(reply=reply, confirmation=confirmation)
        if phase == "PIN":
            return f.pin_context(pin=PinContext(result=pin_result, sessionFailures=0, locked=locked),
                                 reply=reply, confirmation=confirmation)
        return f.confirmation_context(reply=reply, confirmation=confirmation)

    def _pay_permitido(self, phase, mode, reply, phrase, voice_status, pin_result):
        if phase == "CONFIRMATION":
            if mode in (None, "REPLY"):
                return reply == "YES"  # (a) REPLY con "sí"
            return phrase in (0.80, 1.0) and voice_status == "VERIFIED" and reply != "NO"  # (b)
        if phase == "PIN":
            return pin_result == "OK" and mode == "CHALLENGE" and phrase in (0.80, 1.0)  # (c)
        return False  # COMMAND nunca paga

    def test_barrido_de_combinaciones_ningun_pay_fuera_de_los_tres_caminos(self):
        for phase in ("COMMAND", "PIN", "CONFIRMATION"):
            for mode in self.MODES:
                for reply in self.REPLIES:
                    for phrase in self.PHRASES:
                        for voice_status in self.VOICES:
                            for pin_result in self.PINS:
                                for attempts in (0, 1, 5):
                                    for locked in (False, True):
                                        context = self._context(phase, mode, reply, phrase,
                                                                voice_status, pin_result, attempts, locked)
                                        try:
                                            decision = decide(context)
                                        except InvalidContextError:
                                            continue  # contexto imposible: no paga
                                        if decision.decision.value == "PAY":
                                            self.assertTrue(
                                                self._pay_permitido(phase, mode, reply, phrase,
                                                                    voice_status, pin_result),
                                                f"PAY ilegal: {phase}/{mode}/{reply}/{phrase}/"
                                                f"{voice_status}/{pin_result}")


class Determinismo(unittest.TestCase):
    def test_el_mismo_context_da_la_misma_decision(self):
        for context in (ctx_desafio(phrase_score=0.9), ctx_desafio(phrase_score=0.1, attempts=1),
                        ctx_pin_desafio()):
            first = decide(context)
            second = decide(context)
            self.assertEqual(first, second)


def payload(**overrides):
    data = {
        "phase": "CONFIRMATION",
        "intent": f.INTENT_D,
        "resolution": f.RESOLUTION_RESOLVED_LADELA,
        "voice": {"status": "NOT_AVAILABLE", "score": None},
        "enrolled": False,
        "hasBudgetGrant": True,
        "quote": {"debitAmount": f.AMOUNT_DEBIT_WITHIN, "receiveAmount": f.AMOUNT_TWENTY_THOUSAND,
                  "exceedsRemaining": False},
        "pendingPayment": None,
        "now": f.NOW,
        "reply": None,
        "unclearReplies": 0,
        "pin": {"result": None, "sessionFailures": 0, "locked": False},
        "transcriptConfidence": None,
        "intentConfidence": None,
        "config": {"highAmountThreshold": None, "pendingWindowSeconds": 120,
                   "minIntentConfidence": None, "minTranscriptConfidence": None},
    }
    data.update(overrides)
    return data


CONFIRMATION_OK = {"mode": "CHALLENGE", "phraseScore": 1.0,
                   "voice": {"status": "VERIFIED", "score": None}, "challengeAttempts": 0}


class ParseoDeLaConfirmacion(unittest.TestCase):
    def test_json_valido_con_desafio_paga(self):
        self.assertEqual(decide_dict(payload(confirmation=CONFIRMATION_OK)),
                         {"decision": "PAY", "reason": "CONFIRMED"})

    def test_confirmation_null_y_ausente_son_none(self):
        self.assertIsNone(parse_context(payload(confirmation=None)).confirmation)
        self.assertIsNone(parse_context(payload()).confirmation)
        self.assertEqual(decide_dict(payload(reply="YES", confirmation=None)),
                         {"decision": "PAY", "reason": "CONFIRMED"})

    def test_config_de_challenge_se_parsea_con_defaults(self):
        ctx = parse_context(payload(confirmation=CONFIRMATION_OK))
        self.assertFalse(ctx.config.confirmation_challenge)  # apagada por defecto
        self.assertEqual(ctx.config.challenge_phrase_match_min, 0.80)
        ctx_on = parse_context(payload(config={"highAmountThreshold": None, "pendingWindowSeconds": 120,
                                               "minIntentConfidence": None, "minTranscriptConfidence": None,
                                               "confirmationChallenge": True, "challengePhraseMatchMin": 0.9}))
        self.assertTrue(ctx_on.config.confirmation_challenge)
        self.assertEqual(ctx_on.config.challenge_phrase_match_min, 0.9)

    def test_phrase_score_invalido_falla_cerrado(self):
        for bad in (1.5, -0.1, "0.9", True, float("nan"), float("inf"), {}):
            with self.assertRaises(InvalidContextError):
                parse_context(payload(confirmation={**CONFIRMATION_OK, "phraseScore": bad}))

    def test_challenge_attempts_invalido_falla_cerrado(self):
        for bad in (-1, 1.0, True, None, "2"):
            with self.assertRaises(InvalidContextError):
                parse_context(payload(confirmation={**CONFIRMATION_OK, "challengeAttempts": bad}))

    def test_modo_desconocido_y_modo_faltante_fallan_cerrado(self):
        with self.assertRaises(InvalidContextError):
            parse_context(payload(confirmation={**CONFIRMATION_OK, "mode": "CONFIRMAR"}))
        sin_mode = {k: v for k, v in CONFIRMATION_OK.items() if k != "mode"}
        with self.assertRaises(InvalidContextError):
            parse_context(payload(confirmation=sin_mode))

    def test_voice_mal_formada_y_confirmation_no_dict_fallan_cerrado(self):
        with self.assertRaises(InvalidContextError):
            parse_context(payload(confirmation={**CONFIRMATION_OK, "voice": {"status": "MAYBE", "score": None}}))
        with self.assertRaises(InvalidContextError):
            parse_context(payload(confirmation="not-a-dict"))

    def test_config_de_challenge_invalida_falla_cerrado(self):
        base_config = {"highAmountThreshold": None, "pendingWindowSeconds": 120,
                       "minIntentConfidence": None, "minTranscriptConfidence": None}
        for bad_config in (
            {**base_config, "challengePhraseMatchMin": 1.5},
            {**base_config, "challengePhraseMatchMin": "0.8"},
            {**base_config, "challengePhraseMatchMin": True},
            {**base_config, "confirmationChallenge": "yes"},
        ):
            with self.assertRaises(InvalidContextError):
                parse_context(payload(config=bad_config))

    def test_los_errores_no_llevan_el_valor_recibido(self):
        probes = [
            ("phraseScore", 1.5), ("phraseScore", "0.9"), ("challengeAttempts", -1),
        ]
        for clave, valor in probes:
            try:
                parse_context(payload(confirmation={**CONFIRMATION_OK, clave: valor}))
                self.fail("debía fallar")
            except InvalidContextError as exc:
                self.assertNotIn(str(valor), str(exc))


class MapeosDeSayConDesafio(unittest.TestCase):
    def test_retry_failed_y_voice_not_verified(self):
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.CHALLENGE_RETRY),
                                       ctx_desafio(phrase_score=0.1, attempts=0)), "CHALLENGE_RETRY")
        self.assertEqual(say_situation(Decision(DecisionType.REJECT, Reason.CHALLENGE_FAILED),
                                       ctx_desafio(phrase_score=0.1, attempts=1)), "CHALLENGE_FAILED")
        self.assertEqual(say_situation(Decision(DecisionType.ASK_PIN, Reason.CHALLENGE_VOICE_NOT_VERIFIED),
                                       ctx_desafio(phrase_score=0.9, voice_status="BELOW_THRESHOLD")),
                         "PIN_KEYBOARD")

    def test_confirmed_with_pin_no_tiene_situacion_como_confirmed(self):
        self.assertIsNone(say_situation(Decision(DecisionType.PAY, Reason.CONFIRMED_WITH_PIN),
                                        ctx_pin_desafio()))

    def test_confirm_challenge_y_overrun(self):
        ctx = f.command_context(voice=f.Voice(status="VERIFIED", score=0.9), enrolled=True,
                                confirmation=challenge_confirmation())
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED), ctx),
                         "CONFIRM_CHALLENGE")
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED),
                                       f.command_context(voice=f.Voice(status="VERIFIED", score=0.9), enrolled=True,
                                                         quote=f.QUOTE_EXCEEDS_BUDGET,
                                                         confirmation=challenge_confirmation())),
                         "CONFIRM_CHALLENGE_OVERRUN")

    def test_confirm_challenge_para_pending_payment_unconfirmed(self):
        base = {"voice": f.Voice(status="VERIFIED", score=0.9), "enrolled": True,
                "pendingPayment": f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
                "confirmation": challenge_confirmation()}
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED),
                                       f.command_context(**base)), "CONFIRM_CHALLENGE")
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED),
                                       f.command_context(**{**base, "quote": f.QUOTE_EXCEEDS_BUDGET})),
                         "CONFIRM_CHALLENGE_OVERRUN")

    def test_pin_correct_con_confirmation_challenge_queda_como_hoy(self):
        ctx = f.pin_context(confirmation=challenge_confirmation())
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.PIN_CORRECT), ctx),
                         "CONFIRM")

    def test_con_reply_o_sin_confirmation_los_mapeos_no_cambian(self):
        ctx = f.command_context(voice=f.Voice(status="VERIFIED", score=0.9), enrolled=True,
                                confirmation=challenge_confirmation(mode="REPLY"))
        self.assertEqual(say_situation(Decision(DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED), ctx),
                         "CONFIRM")


class SituacionesPendientesDeVoz(unittest.TestCase):
    def test_las_cuatro_del_desafio_estan_en_new_y_ya_no_hay_pendientes(self):
        # Voz agregó CONFIRM_CHALLENGE_OVERRUN y CHALLENGE_FAILED (17 oct): el set queda vacío.
        self.assertEqual(PENDING_VOZ_SITUATIONS, frozenset())
        self.assertTrue({"CONFIRM_CHALLENGE", "CONFIRM_CHALLENGE_OVERRUN", "CHALLENGE_RETRY",
                         "CHALLENGE_FAILED"}.issubset(set(VOICE_SITUATIONS_NEW)))

    def test_si_voz_agrega_una_pendiente_hay_que_quitarla_del_set(self):
        try:
            from voice import phrases
        except ImportError:
            self.skipTest("voice/phrases.py no está en esta rama todavía")
        nombres = {situacion.value for situacion in phrases.Situation}
        ya_existentes = PENDING_VOZ_SITUATIONS & nombres
        self.assertEqual(
            ya_existentes, set(),
            "Voz ya tiene esas situaciones: quítalas de PENDING_VOZ_SITUATIONS en say_map.py")


if __name__ == "__main__":
    unittest.main()