"""R2 — el contexto del motor se arma exactamente como lo espera api/decision.

Cada campo cita su fuente: la intención sale de api/voice (extract_intent), la
agenda de api/voice (resolve_recipient), la voz del puerto SpeakerVerifier, la
quote del cliente de Node (Contrato A), now del reloj inyectado y la
configuración del entorno (ASSET_CODE/ASSET_SCALE solo del entorno, CONV-1).
"""
import os
from datetime import datetime, timezone
from unittest import mock
import unittest

from decision import InvalidContextError, decide_dict

from app.engine_context import build_context
from voice.config import ASSET

import node_double


class FakeClockPort:
    def __init__(self, instant: datetime):
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


DEFAULT_QUOTE = {
    "quoteId": node_double.QUOTE_ID,
    "debitAmount": node_double.AMOUNT_DEBIT_WITHIN,
    "receiveAmount": node_double.AMOUNT_RECEIVE,
    "exceedsRemaining": False,
}


class ContextBuildTest(unittest.TestCase):
    def context(self, *, text="envíale veinte mil a mi hija", has_budget_grant=True,
                quote=DEFAULT_QUOTE, voice_status="NOT_AVAILABLE", voice_score=None, enrolled=True,
                pending_payment=None, clock=None, env_asset=("COP", "2")):
        with mock.patch.dict(os.environ, {"ASSET_CODE": env_asset[0], "ASSET_SCALE": env_asset[1]}, clear=True):
            return build_context(
                phase="COMMAND",
                input_text=text,
                voice_status=voice_status,
                voice_score=voice_score,
                enrolled=enrolled,
                has_budget_grant=has_budget_grant,
                quote=quote,
                pending_payment=pending_payment,
                clock=clock or FakeClockPort(datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)),
                agenda=None,
            )

    def test_every_context_field_cites_its_source(self):
        data = self.context()
        self.assertEqual(set(data), {
            "phase", "intent", "resolution", "voice", "enrolled", "hasBudgetGrant", "quote",
            "pendingPayment", "now", "reply", "unclearReplies", "pin", "transcriptConfidence",
            "intentConfidence", "config",
        })
        self.assertEqual(data["phase"], "COMMAND")
        # intención: extract_intent de api/voice sobre el texto del turno
        self.assertEqual(data["intent"], {
            "action": "PAY",
            "amount": {"value": "2000000", "assetCode": "COP", "assetScale": 2},
            "amountError": None,
            "recipient": "mi hija",
            "status": "OK",
        })
        # agenda: resolve_recipient de api/voice contra la agenda provisional
        self.assertEqual(data["resolution"], {
            "kind": "RESOLVED",
            "contact": {
                "alias": "mi-hija",
                "name": "Laura hija",
                "walletAddress": "https://ilp.interledger-test.dev/ezpay-placeholder-laura-hija",
                "previouslyPaid": True,
            },
        })
        # voz: text -> NOT_AVAILABLE (regla de ML 2)
        self.assertEqual(data["voice"], {"status": "NOT_AVAILABLE", "score": None})
        self.assertEqual(data["now"], "2026-10-17T12:00:00+00:00")
        self.assertEqual(data["pin"], {"result": None, "sessionFailures": 0, "locked": False})
        self.assertEqual(data["config"], {
            "highAmountThreshold": None,
            "pendingWindowSeconds": 120,
            "minIntentConfidence": None,
            "minTranscriptConfidence": None,
        })

    def test_context_is_parseable_and_the_engine_answers(self):
        data = self.context()
        decision = decide_dict(data)  # no lanza InvalidContextError
        self.assertEqual(decision["decision"], "ASK_PIN")  # text -> NOT_AVAILABLE -> ASK_PIN

    def test_voice_status_comes_from_the_speaker_verifier_port(self):
        data = self.context(voice_status="VERIFIED", voice_score=0.87)
        self.assertEqual(data["voice"], {"status": "VERIFIED", "score": 0.87})

    def test_amounts_use_the_environment_not_constants(self):
        data = self.context(env_asset=("EUR", "0"), text="envíale cien a mi hija")
        self.assertEqual(data["intent"]["amount"], {"value": "100", "assetCode": "EUR", "assetScale": 0})

    def test_quote_is_null_without_budget_grant(self):
        data = self.context(has_budget_grant=False, quote=None)
        self.assertIsNone(data["quote"])
        decision = decide_dict(data)
        self.assertEqual((decision["decision"], decision["reason"]), ("REQUIRE_AUTH", "NO_BUDGET_GRANT"))

    def test_pending_payment_enters_the_context(self):
        pending = {
            "recipient": "https://wallet.test/laura",
            "createdAt": "2026-10-17T11:59:00+00:00",
            "status": "PROCESSING",
        }
        data = self.context(pending_payment=pending)
        self.assertEqual(data["pendingPayment"], pending)

    def test_now_is_the_injected_clock(self):
        clock = FakeClockPort(datetime(2026, 10, 17, 15, 30, 41, tzinfo=timezone.utc))
        data = self.context(clock=clock)
        self.assertEqual(data["now"], "2026-10-17T15:30:41+00:00")

    def test_impossible_context_never_reaches_the_engine(self):
        data = build_context(
            phase="COMMAND",
            input_text="envíale veinte mil a mi hija",
            voice_status="INVALID",
            voice_score=None,
            enrolled=False,
            has_budget_grant=True,
            quote=None,
            pending_payment=None,
            clock=FakeClockPort(datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)),
            agenda=None,
        )
        with self.assertRaises(InvalidContextError):
            decide_dict(data)  # fail-closed: el orquestador nunca decide con un contexto roto


if __name__ == "__main__":
    unittest.main()