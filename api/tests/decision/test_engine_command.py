"""Escenarios de la tabla de la fase COMMAND del spec decision-engine."""
import unittest

from decision.engine import decide
from decision.models import (
    Amount,
    Decision,
    DecisionType,
    PinContext,
    Quote,
    Reason,
    Resolution,
    Voice,
)
import decision_fixtures as f


class Cancelacion(unittest.TestCase):
    def test_cancelacion(self):
        ctx = f.command_context(intent=f.intent(action="CANCEL"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.CANCELLED_BY_USER))


class Regla2IntencionInvalida(unittest.TestCase):
    def test_accion_desconocida(self):
        ctx = f.command_context(intent=f.intent(action="UNKNOWN"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_UNKNOWN))

    def test_monto_con_demasiados_decimales(self):
        ctx = f.command_context(intent=f.intent(amountError="TOO_MANY_DECIMALS"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.AMOUNT_ERROR))

    def test_prioridad_dentro_de_la_regla_2(self):
        ctx = f.command_context(intent=f.intent(action="UNKNOWN", amountError="INVALID_AMOUNT"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_UNKNOWN))

    def test_dos_montos_dichos(self):
        ctx = f.command_context(intent=f.intent(status="AMBIGUOUS", amount=None))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_AMBIGUOUS))

    def test_dos_destinatarios_dichos(self):
        ctx = f.command_context(intent=f.intent(status="AMBIGUOUS", recipient=None))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_AMBIGUOUS))

    def test_sin_monto(self):
        ctx = f.command_context(intent=f.intent(amount=None, status="UNCLEAR"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.AMOUNT_MISSING))

    def test_sin_monto_con_status_ok_da_lo_mismo(self):
        ctx = f.command_context(intent=f.intent(amount=None, status="OK"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.AMOUNT_MISSING))

    def test_sin_destinatario(self):
        ctx = f.command_context(intent=f.intent(recipient=None, status="UNCLEAR"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.RECIPIENT_MISSING))

    def test_sin_destinatario_con_status_ok_da_lo_mismo(self):
        ctx = f.command_context(intent=f.intent(recipient=None, status="OK"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.RECIPIENT_MISSING))

    def test_hola_produce_intencion_desconocida(self):
        ctx = f.command_context(intent=f.intent(action="UNKNOWN", amount=None, recipient=None, status="OK"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_UNKNOWN))

    def test_cancelar_produce_reject(self):
        ctx = f.command_context(intent=f.intent(action="CANCEL", amount=None, recipient=None, status="OK"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.CANCELLED_BY_USER))

    def test_intencion_poco_clara(self):
        ctx = f.command_context(intent=f.intent(status="UNCLEAR"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_UNCLEAR))


class Regla2bCortesDeConfianza(unittest.TestCase):
    def test_intencion_con_confianza_baja(self):
        ctx = f.command_context(
            config=f.config(minIntentConfidence=0.7, minTranscriptConfidence=0.5),
            intentConfidence=0.4,
            transcriptConfidence=0.9,
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.INTENT_LOW_CONFIDENCE))

    def test_transcripcion_con_confianza_baja(self):
        ctx = f.command_context(
            config=f.config(minIntentConfidence=0.7, minTranscriptConfidence=0.5),
            intentConfidence=0.7,
            transcriptConfidence=0.2,
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.TRANSCRIPT_LOW_CONFIDENCE))

    def test_cortes_desactivados(self):
        ctx = f.command_context(intentConfidence=0.01, transcriptConfidence=0.01)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))

    def test_puntaje_nulo_con_corte_activo(self):
        ctx = f.command_context(
            config=f.config(minIntentConfidence=0.7, minTranscriptConfidence=0.5),
            intentConfidence=None,
            transcriptConfidence=None,
        )
        result = decide(ctx)
        self.assertEqual(result.reason, Reason.VOICE_NOT_VERIFIED)

    def test_buena_confianza_no_sustituye_la_verificacion_de_voz(self):
        ctx = f.command_context(
            config=f.config(minIntentConfidence=0.7, minTranscriptConfidence=0.5),
            intentConfidence=0.9,
            transcriptConfidence=0.9,
            voice=Voice(status="NOT_AVAILABLE"),
            enrolled=False,
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))


class Reglas3y4Agenda(unittest.TestCase):
    def test_destinatario_fuera_de_la_agenda(self):
        ctx = f.command_context(resolution=Resolution(kind="NOT_FOUND"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.RECIPIENT_NOT_FOUND))

    def test_dos_coincidencias_en_la_agenda(self):
        ctx = f.command_context(resolution=f.resolution_choice("Laura hija", "Laura vecina"))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_RECIPIENT, Reason.RECIPIENT_AMBIGUOUS))


class Regla5SinGrant(unittest.TestCase):
    def test_sin_grant_de_presupuesto(self):
        ctx = f.command_context(hasBudgetGrant=False, quote=None)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REQUIRE_AUTH, Reason.NO_BUDGET_GRANT))


class Regla6PagoPendienteDentroDeLaVentana(unittest.TestCase):
    def test_pago_pendiente_al_mismo_destinatario_dentro_de_la_ventana(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_WITHIN_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REASK, Reason.PENDING_PAYMENT_SAME_RECIPIENT))

    def test_borde_de_la_ventana_cuenta_como_dentro(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_AT_WINDOW_EDGE),
        )
        result = decide(ctx)
        self.assertEqual(result.reason, Reason.PENDING_PAYMENT_SAME_RECIPIENT)

    def test_pago_pendiente_a_otro_destinatario(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(recipient=f.LUCIA.walletAddress, createdAt=f.CREATED_PAST_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED))

    def test_pago_pendiente_completed_o_failed_no_avisa(self):
        for status in ("COMPLETED", "FAILED"):
            ctx = f.command_context(
                voice=Voice(status="VERIFIED", score=0.8),
                enrolled=True,
                pendingPayment=f.pending_payment(status=status, createdAt=f.CREATED_PAST_WINDOW),
            )
            result = decide(ctx)
            self.assertEqual(
                (result.decision, result.reason),
                (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED),
                status,
            )

    def test_pago_sin_payment_id_cuenta_como_processing(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_WITHIN_WINDOW, status="PROCESSING"),
        )
        self.assertEqual(decide(ctx).reason, Reason.PENDING_PAYMENT_SAME_RECIPIENT)


class Regla6bAvisoPostVentana(unittest.TestCase):
    def test_pago_pendiente_pasado_el_tope_marca_warn(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED))

    def test_aviso_post_ventana_con_voz_verificada(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED))

    def test_la_advertencia_no_salta_el_pin(self):
        ctx = f.command_context(pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))
        pin_ok = f.pin_context(
            pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
            pin=PinContext(result="OK", sessionFailures=0, locked=False),
        )
        result = decide(pin_ok)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED))

    def test_aviso_post_ventana_con_exceso_de_presupuesto(self):
        ctx = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            quote=f.QUOTE_EXCEEDS_BUDGET,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED))
        yes_ctx = f.confirmation_context(quote=f.QUOTE_EXCEEDS_BUDGET, reply="YES")
        result = decide(yes_ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REQUIRE_AUTH, Reason.CONFIRMED_NEEDS_WALLET_AUTH))

    def test_no_ante_la_advertencia(self):
        ctx = f.confirmation_context(reply="NO")
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.USER_DECLINED))

    def test_ui_liberada_tras_no_pude_confirmar(self):
        inside = f.command_context(
            voice=Voice(status="VERIFIED", score=0.8),
            enrolled=True,
            pendingPayment=f.pending_payment(createdAt=f.CREATED_WITHIN_WINDOW),
        )
        self.assertEqual(decide(inside).reason, Reason.PENDING_PAYMENT_SAME_RECIPIENT)
        outside = f.command_context(pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW))
        self.assertEqual(decide(outside).reason, Reason.VOICE_NOT_VERIFIED)


class Regla7VozNoVerificada(unittest.TestCase):
    def test_comando_por_texto_pide_pin(self):
        ctx = f.command_context(voice=Voice(status="NOT_AVAILABLE"), enrolled=True)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))

    def test_usuario_no_enrolado(self):
        ctx = f.command_context(voice=Voice(status="NOT_AVAILABLE", score=None), enrolled=False)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))

    def test_voz_por_debajo_del_umbral(self):
        ctx = f.command_context(voice=Voice(status="BELOW_THRESHOLD", score=0.3), enrolled=True)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))


def verified_command(**overrides):
    base = {
        "voice": Voice(status="VERIFIED", score=0.8),
        "enrolled": True,
    }
    base.update(overrides)
    return f.command_context(**base)


class Regla8DestinatarioNuevoYMontoAlto(unittest.TestCase):
    def test_primer_pago_a_un_destinatario_nuevo(self):
        ctx = verified_command(resolution=f.resolution_resolved(f.LUCIA))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.NEW_RECIPIENT))

    def test_monto_alto(self):
        quote = Quote(debitAmount=Amount("6015000", "COP", 2), receiveAmount=Amount("6000000", "COP", 2), exceedsRemaining=False)
        ctx = verified_command(quote=quote, config=f.config(highAmountThreshold=f.FIFTY_THOUSAND_COP))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.HIGH_AMOUNT))

    def test_destinatario_nuevo_tiene_prioridad_sobre_monto_alto(self):
        quote = Quote(debitAmount=Amount("6015000", "COP", 2), receiveAmount=Amount("6000000", "COP", 2), exceedsRemaining=False)
        ctx = verified_command(
            resolution=f.resolution_resolved(f.LUCIA),
            quote=quote,
            config=f.config(highAmountThreshold=f.FIFTY_THOUSAND_COP),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.NEW_RECIPIENT))

    def test_umbral_nulo_desactiva_el_corte_por_monto(self):
        ctx = verified_command(config=f.config(highAmountThreshold=None))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED))

    def test_exceso_de_presupuesto_no_pide_pin_por_monto(self):
        ctx = verified_command(quote=f.QUOTE_EXCEEDS_BUDGET, config=f.config(highAmountThreshold=f.FIFTY_THOUSAND_COP))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED))


class Regla9Resto(unittest.TestCase):
    def test_caso_feliz_de_la_demo(self):
        ctx = verified_command()
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED))
        yes_ctx = f.confirmation_context(reply="YES")
        self.assertEqual(decide(yes_ctx), Decision(DecisionType.PAY, Reason.CONFIRMED))

    def test_exceso_de_presupuesto_va_a_la_wallet_sin_pin_por_monto(self):
        ctx = verified_command(quote=f.QUOTE_EXCEEDS_BUDGET)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.ALL_CHECKS_PASSED))
        yes_ctx = f.confirmation_context(quote=f.QUOTE_EXCEEDS_BUDGET, reply="YES")
        result = decide(yes_ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REQUIRE_AUTH, Reason.CONFIRMED_NEEDS_WALLET_AUTH))

    def test_flujo_h1_por_texto(self):
        ctx = f.command_context()
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.VOICE_NOT_VERIFIED))
        pin_ok = f.pin_context(pin=PinContext(result="OK", sessionFailures=0, locked=False))
        result = decide(pin_ok)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PIN_CORRECT))
        result = decide(f.confirmation_context(reply="YES"))
        self.assertEqual((result.decision, result.reason), (DecisionType.PAY, Reason.CONFIRMED))