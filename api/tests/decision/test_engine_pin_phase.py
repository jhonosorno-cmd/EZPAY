"""Escenarios de la tabla de la fase PIN del spec decision-engine."""
import unittest

from decision.engine import decide
from decision.models import DecisionType, PinContext, Reason
import decision_fixtures as f


class TablaFasePin(unittest.TestCase):
    def test_pin_bloqueado(self):
        ctx = f.pin_context(pin=PinContext(result=None, sessionFailures=0, locked=True))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.PIN_LOCKED))

    def test_pin_correcto_no_reemplaza_el_si(self):
        ctx = f.pin_context(pin=PinContext(result="OK", sessionFailures=0, locked=False))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PIN_CORRECT))
        self.assertNotEqual(result.decision, DecisionType.PAY)

    def test_pin_correcto_con_pago_pendiente_pasado_el_tope(self):
        ctx = f.pin_context(
            pin=PinContext(result="OK", sessionFailures=0, locked=False),
            pendingPayment=f.pending_payment(createdAt=f.CREATED_PAST_WINDOW),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PENDING_PAYMENT_UNCONFIRMED))

    def test_primer_intento_fallido(self):
        ctx = f.pin_context(pin=PinContext(result="WRONG", sessionFailures=1, locked=False))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.PIN_WRONG))

    def test_intentos_de_la_sesion_agotados(self):
        ctx = f.pin_context(pin=PinContext(result="WRONG", sessionFailures=3, locked=False))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.PIN_ATTEMPTS_EXHAUSTED))

    def test_pin_con_formato_invalido(self):
        ctx = f.pin_context(pin=PinContext(result="INVALID_FORMAT", sessionFailures=0, locked=False))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.PIN_INVALID_FORMAT))

    def test_pin_result_nulo(self):
        ctx = f.pin_context(pin=PinContext(result=None, sessionFailures=0, locked=False))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_PIN, Reason.PIN_INVALID_FORMAT))

    def test_la_fase_pin_no_reevalua_la_tabla_command(self):
        ctx = f.pin_context(
            intent=f.intent(action="UNKNOWN"),
            resolution=f.Resolution(kind="NOT_FOUND"),
            hasBudgetGrant=False,
            quote=None,
            pin=PinContext(result="OK", sessionFailures=0, locked=False),
        )
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.PIN_CORRECT))