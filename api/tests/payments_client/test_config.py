"""Configuration tests (brief e): asset code and scale only from the environment."""
import os
from unittest import mock
import unittest

import httpx

import doubles

CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in ("ASSET_CODE", "ASSET_SCALE", "NODE_BASE_URL")}


class ConfigTest(unittest.TestCase):
    def client(self, recorder, **overrides):
        return doubles.make_client(
            recorder,
            lambda request: httpx.Response(200, json={"ok": True}),
            **overrides,
        )

    def test_missing_asset_code_does_not_start(self):
        with mock.patch.dict(os.environ, {**CLEAN_ENV, "ASSET_SCALE": "2"}, clear=True):
            with self.assertRaises(Exception) as ctx:
                self.client(doubles.Recorder())
            self.assertIn("ASSET_CODE", str(ctx.exception))

    def test_missing_asset_scale_does_not_start(self):
        with mock.patch.dict(os.environ, {**CLEAN_ENV, "ASSET_CODE": "COP"}, clear=True):
            with self.assertRaises(Exception) as ctx:
                self.client(doubles.Recorder())
            self.assertIn("ASSET_SCALE", str(ctx.exception))

    def test_missing_both_does_not_start(self):
        with mock.patch.dict(os.environ, CLEAN_ENV, clear=True):
            with self.assertRaises(Exception):
                self.client(doubles.Recorder())

    def test_non_integer_asset_scale_does_not_start(self):
        for scale in ("2.0", "pesos", "-1"):
            with mock.patch.dict(os.environ, {**CLEAN_ENV, "ASSET_CODE": "COP", "ASSET_SCALE": scale}, clear=True):
                with self.assertRaises(Exception):
                    self.client(doubles.Recorder())

    def test_amounts_are_built_from_the_environment(self):
        recorder = doubles.Recorder()
        with mock.patch.dict(
            os.environ,
            {**CLEAN_ENV, "NODE_BASE_URL": "http://node.test/v1", "ASSET_CODE": "COP", "ASSET_SCALE": "2"},
            clear=True,
        ):
            client = self.client(recorder)
        client.create_quote("g_abc", "https://wallet.test/laura", "2000000")
        self.assertEqual(
            recorder.body(0)["receiveAmount"],
            {"value": "2000000", "assetCode": "COP", "assetScale": 2},
        )

    def test_currency_is_not_hardcoded(self):
        recorder = doubles.Recorder()
        with mock.patch.dict(
            os.environ,
            {**CLEAN_ENV, "NODE_BASE_URL": "http://node.test/v1", "ASSET_CODE": "EUR", "ASSET_SCALE": "0"},
            clear=True,
        ):
            client = self.client(recorder)
        client.create_quote("g_abc", "https://wallet.test/laura", "100")
        self.assertEqual(
            recorder.body(0)["receiveAmount"],
            {"value": "100", "assetCode": "EUR", "assetScale": 0},
        )

    def test_default_node_base_url_is_contract_a(self):
        with mock.patch.dict(os.environ, {**CLEAN_ENV, "ASSET_CODE": "COP", "ASSET_SCALE": "2"}, clear=True):
            client = self.client(doubles.Recorder())
        self.assertEqual(client.base_url, "http://localhost:4000/v1")


if __name__ == "__main__":
    unittest.main()