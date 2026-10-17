"""Desafío de voz en la confirmación (B11, add-ml2-integration voice-turn-integration y la tabla
CHALLENGE de decision-engine). Voz falsa: el "audio" es el texto dicho; la frase sale del banco real."""
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app_doubles import amt, build, contract_schema
import jsonschema

TURN = contract_schema("TurnResponse")


class ChallengeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch, self.node, self.voice, self.pin = build(Path(self._tmp.name), challenge=True)
        self.client = TestClient(create_app(orchestrator=self.orch, voice_io=self.voice))
        self.client.post("/api/budget", json={"debitAmount": amt("20000000")})
        self.client.post("/api/grant-callback", json={"interactRef": "r", "hash": "h"})

    def turn(self, sid=None, text=None, audio=None):
        data = {"sessionId": sid} if sid else {}
        if text is not None:
            data["text"] = text
        files = {"audio": ("a.webm", io.BytesIO(audio.encode()), "audio/webm")} if audio is not None else None
        body = self.client.post("/api/turns", data=data, files=files).json()
        jsonschema.validate(body, TURN)
        return body

    def ask(self):
        body = self.turn(audio="envíale veinte mil a mi hija")  # voz VERIFIED, destinatario conocido
        self.assertEqual(body["state"], "AWAITING_CONFIRMATION")
        self.assertTrue(body["challengePhrase"])
        self.assertIn(body["challengePhrase"], body["say"])  # CONFIRM_CHALLENGE lleva la frase
        return body

    def test_repeating_the_phrase_with_the_verified_voice_pays(self):
        body = self.ask()
        done = self.turn(body["sessionId"], audio=body["challengePhrase"])
        self.assertEqual(done["state"], "COMPLETED")
        self.assertIsNone(done["challengePhrase"])

    def test_wrong_phrase_retries_once_with_another_phrase_then_rejects(self):
        body = self.ask()
        retry = self.turn(body["sessionId"], audio="el perro come pan en la mesa grande")
        self.assertEqual(retry["state"], "AWAITING_CONFIRMATION")
        self.assertNotEqual(retry["challengePhrase"], body["challengePhrase"])
        self.assertIn(retry["challengePhrase"], retry["say"])  # CHALLENGE_RETRY
        failed = self.turn(body["sessionId"], audio="otra cosa que no es la frase")
        self.assertEqual(failed["state"], "REJECTED")
        self.assertNotIn("create_payment", self.node.names())

    def test_no_rejects(self):
        body = self.ask()
        self.assertEqual(self.turn(body["sessionId"], audio="no")["state"], "REJECTED")
        self.assertNotIn("create_payment", self.node.names())

    def test_typed_yes_is_not_a_spoken_challenge(self):
        body = self.ask()
        retry = self.turn(body["sessionId"], text="sí")  # phraseScore null: no hubo respuesta por voz
        self.assertEqual(retry["state"], "AWAITING_CONFIRMATION")
        self.assertNotIn("create_payment", self.node.names())

    def test_right_phrase_other_voice_asks_pin_and_pin_pays(self):
        body = self.ask()
        self.voice.voice_status = "BELOW_THRESHOLD"  # la voz de la respuesta no coincide
        pin = self.turn(body["sessionId"], audio=body["challengePhrase"])
        self.assertEqual(pin["state"], "AWAITING_PIN")
        self.assertNotIn("create_payment", self.node.names())
        done = self.turn(body["sessionId"], text="4826")  # CONFIRMED_WITH_PIN: sin otro "sí"
        self.assertEqual(done["state"], "COMPLETED")

    def test_payment_that_went_through_pin_confirms_with_yes(self):
        body = self.turn(text="envíale veinte mil a mi hija")  # texto: PIN primero (D3)
        self.assertEqual(body["state"], "AWAITING_PIN")
        confirm = self.turn(body["sessionId"], text="4826")
        self.assertEqual(confirm["state"], "AWAITING_CONFIRMATION")
        self.assertIsNone(confirm["challengePhrase"])  # modo REPLY: no hay ciclos de PIN
        self.assertEqual(self.turn(body["sessionId"], text="sí")["state"], "COMPLETED")

    def test_phrases_are_not_repeated_in_the_session(self):
        first = self.ask()
        self.turn(first["sessionId"], audio=first["challengePhrase"])
        second = self.turn(first["sessionId"], audio="envíale veinte mil a mi hija")
        self.assertNotEqual(second["challengePhrase"], first["challengePhrase"])


if __name__ == "__main__":
    unittest.main()
