"""Rutas del Contrato B y orquestador del turno (turn-orchestration, payments-client).

Correr desde api/: PYTHONPATH=. python -m unittest discover -s tests/app -v
"""
import io
import logging
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("EZPAY_WARMUP_WHISPER", "0")

import jsonschema
from fastapi.testclient import TestClient

from app.main import create_app
from app_doubles import build, contract_schema, temp_dir

TURN = contract_schema("TurnResponse")
ERROR = contract_schema("ErrorBody")
BUDGET = contract_schema("Budget")


class AppCase(unittest.TestCase):
    def setUp(self):
        self._tmp = temp_dir()
        self.orch, self.node, self.voice, self.pin = build(Path(self._tmp.name))
        self.client = TestClient(create_app(orchestrator=self.orch, voice_io=self.voice))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self._tmp.cleanup()

    # ---------------------------------------------------------------- ayudas
    def turn(self, sid=None, text=None, audio=None, kind=None, status=200):
        data = {}
        if sid:
            data["sessionId"] = sid
        if text is not None:
            data["text"] = text
        if kind is not None:
            data["kind"] = kind
        files = {"audio": ("command.webm", io.BytesIO(audio.encode()), "audio/webm")} if audio is not None else None
        res = self.client.post("/api/turns", data=data, files=files)
        self.assertEqual(res.status_code, status, res.text)
        body = res.json()
        jsonschema.validate(body, TURN if status == 200 else ERROR)
        return body

    def approve(self):
        res = self.client.post("/api/grant-callback", json={"interactRef": "ref-1", "hash": "hash-1"})
        self.assertEqual(res.status_code, 200)
        jsonschema.validate(res.json(), TURN)
        return res.json()

    def with_budget(self):
        res = self.client.post("/api/budget", json={"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}})
        self.assertEqual(res.status_code, 201)
        body = self.approve()
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.node.calls.clear()


class TestInputErrors(AppCase):
    def test_neither_audio_nor_text(self):
        body = self.turn(status=400)
        self.assertEqual(body["error"]["code"], "AUDIO_OR_TEXT_REQUIRED")

    def test_both_audio_and_text(self):
        body = self.turn(text="hola", audio="hola", status=400)
        self.assertEqual(body["error"]["code"], "AUDIO_OR_TEXT_REQUIRED")

    def test_unknown_session(self):
        body = self.turn(sid="s_nope", text="hola", status=404)
        self.assertEqual(body["error"]["code"], "SESSION_NOT_FOUND")

    def test_verify_pending_needs_session(self):
        body = self.turn(kind="verify_pending", status=400)
        self.assertEqual(body["error"]["code"], "AUDIO_OR_TEXT_REQUIRED")

    def test_digits_with_lost_session_never_reach_intent(self):
        body = self.turn(sid="s_lost", text="1234")
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.assertNotIn("1234", body["say"])
        self.assertEqual(self.node.calls, [])


class TestBudget(AppCase):
    def test_no_budget_yet(self):
        res = self.client.get("/api/budget")
        self.assertEqual(res.status_code, 200)
        jsonschema.validate(res.json(), BUDGET)
        self.assertEqual(res.json()["status"], "PENDING")

    def test_create_and_read_budget(self):
        self.with_budget()
        res = self.client.get("/api/budget")
        self.assertEqual(res.status_code, 200)
        jsonschema.validate(res.json(), BUDGET)
        self.assertEqual(res.json()["status"], "ACTIVE")

    def test_invalid_amount(self):
        res = self.client.post("/api/budget", json={"debitAmount": {"value": "20.5", "assetCode": "COP", "assetScale": 2}})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["code"], "INVALID_AMOUNT")

    def test_rejected_in_wallet_skips_continue(self):
        self.client.post("/api/budget", json={"debitAmount": {"value": "20000000", "assetCode": "COP", "assetScale": 2}})
        res = self.client.post("/api/grant-callback", json={"result": "grant_rejected"})
        self.assertEqual(res.json()["state"], "REJECTED")
        self.assertNotIn("continue_grant", self.node.names())


class TestCommandFlow(AppCase):
    def test_command_without_budget_asks_authorization_without_quote(self):
        body = self.turn(text="envíale veinte mil a mi hija")
        self.assertEqual(body["state"], "AWAITING_AUTHORIZATION")
        self.assertTrue(body["interactUrl"])
        self.assertNotIn("create_quote", self.node.names())
        # al volver de la wallet se retoma el mismo comando
        resumed = self.approve()
        self.assertEqual(resumed["sessionId"], body["sessionId"])
        self.assertEqual(resumed["state"], "AWAITING_PIN")  # comando por texto: pide PIN (D3)
        self.assertIn("create_quote", self.node.names())

    def test_text_command_pin_confirm_pay(self):
        self.with_budget()
        body = self.turn(text="envíale veinte mil a mi hija")
        self.assertEqual(body["state"], "AWAITING_PIN")
        sid = body["sessionId"]
        with self.assertLogs(level=logging.INFO) as logs:
            wrong = self.turn(sid, text="1111")
        self.assertEqual(wrong["state"], "AWAITING_PIN")
        self.assertIsNone(wrong["transcript"])
        self.assertIn("2 intentos", wrong["say"])
        self.assertFalse(any("1111" in line for line in logs.output))
        ok = self.turn(sid, text="4826")
        self.assertEqual(ok["state"], "AWAITING_CONFIRMATION")
        self.assertIsNone(ok["transcript"])
        self.assertIn("Laura hija", ok["say"])
        done = self.turn(sid, text="sí")
        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(done["payment"]["receiveAmount"]["value"], "2000000")
        self.assertIn("costó", done["say"])

    def test_voice_command_verified_goes_straight_to_confirmation(self):
        self.with_budget()
        body = self.turn(audio="envíale veinte mil a mi hija")
        self.assertEqual(body["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(body["transcript"], "envíale veinte mil a mi hija")
        self.assertIn("20.000 pesos", body["say"])
        done = self.turn(body["sessionId"], audio="sí")
        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(self.voice.transcribed, 2)

    def test_voice_below_threshold_asks_pin(self):
        self.with_budget()
        self.voice.voice_status = "BELOW_THRESHOLD"
        self.assertEqual(self.turn(audio="envíale veinte mil a mi hija")["state"], "AWAITING_PIN")

    def test_audio_in_pin_state_is_discarded(self):
        self.with_budget()
        sid = self.turn(text="envíale veinte mil a mi hija")["sessionId"]
        body = self.turn(sid, audio="cuatro ocho dos seis")
        self.assertEqual(body["state"], "AWAITING_PIN")
        self.assertIsNone(body["transcript"])
        self.assertEqual(self.voice.transcribed, 0)

    def test_no_then_rejected(self):
        self.with_budget()
        sid = self.turn(audio="envíale veinte mil a mi hija")["sessionId"]
        self.assertEqual(self.turn(sid, audio="no")["state"], "REJECTED")
        self.assertNotIn("create_payment", self.node.names())

    def test_unclear_twice_rejects(self):
        self.with_budget()
        sid = self.turn(audio="envíale veinte mil a mi hija")["sessionId"]
        self.assertEqual(self.turn(sid, audio="mmm tal vez")["state"], "AWAITING_CONFIRMATION")
        self.assertEqual(self.turn(sid, audio="no sé")["state"], "REJECTED")

    def test_unknown_recipient_reasks(self):
        self.with_budget()
        body = self.turn(audio="envíale veinte mil a Pedro")
        self.assertEqual(body["state"], "AWAITING_COMMAND")
        self.assertNotIn("create_quote", self.node.names())

    def test_ambiguous_recipient_then_alias(self):
        self.with_budget()
        body = self.turn(audio="envíale veinte mil a Laura")
        self.assertEqual(body["state"], "AWAITING_RECIPIENT_CHOICE")
        self.assertEqual({o["alias"] for o in body["options"]}, {"mi-hija", "laura-vecina"})
        chosen = self.turn(body["sessionId"], text="mi-hija")
        self.assertEqual(chosen["state"], "AWAITING_CONFIRMATION")

    def test_new_recipient_asks_pin(self):
        self.with_budget()
        self.assertEqual(self.turn(audio="envíale veinte mil a José")["state"], "AWAITING_PIN")


class TestExcessAndPending(AppCase):
    def test_excess_uses_one_off_grant_and_cancels_it(self):
        self.with_budget()
        budget_grant = self.orch.wallet.budget_grant_id
        self.node.exceeds = lambda grant_id, receive: grant_id == budget_grant
        body = self.turn(audio="envíale veinte mil a mi hija")
        self.assertEqual(body["state"], "AWAITING_CONFIRMATION")
        auth = self.turn(body["sessionId"], audio="sí")
        self.assertEqual(auth["state"], "AWAITING_AUTHORIZATION")
        grant_call = [c for c in self.node.calls if c[0] == "create_grant"][-1]
        self.assertEqual(grant_call[1], "2015000")  # debitAmount de la quote
        self.assertRegex(grant_call[2], r"^R1/\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ/P1W$")
        done = self.approve()
        self.assertEqual(done["state"], "COMPLETED")
        quotes = [c for c in self.node.calls if c[0] == "create_quote"]
        self.assertNotEqual(quotes[-1][1], budget_grant)  # recotizó con el puntual
        self.assertIn(("cancel_grant", quotes[-1][1]), self.node.calls)

    def test_payment_pending_then_verify(self):
        self.with_budget()
        self.node.payment_pending = True
        sid = self.turn(audio="envíale veinte mil a mi hija")["sessionId"]
        pending = self.turn(sid, audio="sí")
        self.assertEqual(pending["state"], "PAYMENT_PENDING")
        self.assertIsNone(pending["payment"])
        self.node.payment_pending = False
        done = self.turn(sid, kind="verify_pending")
        self.assertEqual(done["state"], "COMPLETED")
        keys = {c[2] for c in self.node.calls if c[0] == "create_payment"}
        self.assertEqual(len(keys), 1)  # misma Idempotency-Key en el reintento


class TestBudgetRenewal(AppCase):
    def test_invalid_budget_is_renewed_for_its_remaining(self):
        self.with_budget()
        old = self.orch.wallet.budget_grant_id
        self.node.grants[old]["remaining"] = {"value": "12345600", "assetCode": "COP", "assetScale": 2}
        self.node.invalid.add(old)
        body = self.turn(audio="envíale veinte mil a mi hija")
        self.assertEqual(body["state"], "AWAITING_AUTHORIZATION")
        grant_call = [c for c in self.node.calls if c[0] == "create_grant"][-1]
        self.assertEqual(grant_call[1], "12345600")  # no le devuelve a la usuaria lo ya gastado


class TestEnrollment(AppCase):
    def test_status(self):
        res = self.client.get("/api/enrollment")
        self.assertEqual(res.json(), {"enrolled": True})

    def test_consent_required_first(self):
        res = self.client.post("/api/enrollment", data={"consent": "false"})
        self.assertEqual(res.json()["error"]["code"], "CONSENT_REQUIRED")

    def test_three_samples_required(self):
        files = [("audio", ("a.webm", io.BytesIO(b"x"), "audio/webm"))]
        res = self.client.post("/api/enrollment", data={"consent": "true"}, files=files)
        self.assertEqual(res.json()["error"]["code"], "SAMPLES_REQUIRED")


if __name__ == "__main__":
    unittest.main()
