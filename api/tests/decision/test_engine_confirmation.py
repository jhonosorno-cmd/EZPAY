"""Escenarios de la tabla de la fase CONFIRMATION del spec decision-engine."""
import unittest

from decision.engine import decide
from decision.models import DecisionType, Reason, Voice
import decision_fixtures as f


class TablaFaseConfirmation(unittest.TestCase):
    def test_si_dentro_del_presupuesto(self):
        ctx = f.confirmation_context(reply="YES")
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.PAY, Reason.CONFIRMED))

    def test_si_con_exceso_de_limite(self):
        ctx = f.confirmation_context(reply="YES", quote=f.QUOTE_EXCEEDS_BUDGET)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REQUIRE_AUTH, Reason.CONFIRMED_NEEDS_WALLET_AUTH))

    def test_no(self):
        ctx = f.confirmation_context(reply="NO")
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.USER_DECLINED))

    def test_primera_respuesta_poco_clara(self):
        ctx = f.confirmation_context(reply="UNCLEAR", unclearReplies=0)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.ASK_CONFIRM, Reason.REPLY_UNCLEAR_ASK_AGAIN))

    def test_segunda_respuesta_poco_clara(self):
        ctx = f.confirmation_context(reply="UNCLEAR", unclearReplies=1)
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.REJECT, Reason.REPLY_UNCLEAR_REJECTED))

    def test_confirmacion_sin_verificacion_de_voz(self):
        ctx = f.confirmation_context(reply="YES", voice=Voice(status="BELOW_THRESHOLD", score=0.2))
        result = decide(ctx)
        self.assertEqual((result.decision, result.reason), (DecisionType.PAY, Reason.CONFIRMED))

    def test_reply_nulo_se_trata_como_unclear(self):
        first = f.confirmation_context(reply=None, unclearReplies=0)
        self.assertEqual((decide(first).decision, decide(first).reason), (DecisionType.ASK_CONFIRM, Reason.REPLY_UNCLEAR_ASK_AGAIN))
        second = f.confirmation_context(reply=None, unclearReplies=1)
        self.assertEqual((decide(second).decision, decide(second).reason), (DecisionType.REJECT, Reason.REPLY_UNCLEAR_REJECTED))