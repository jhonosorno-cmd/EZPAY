"""Script de PIN de demo (scripts/set_demo_pin.py): el hash que genera valida 1234."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import set_demo_pin
from pin.pin import PIN_HASH_ENV, PinValidator


class DemoPinTest(unittest.TestCase):
    def test_line_has_env_name_and_verifies_demo_pin(self):
        line = set_demo_pin.build_env_line()
        name, _, spec = line.partition("=")
        self.assertEqual(name, PIN_HASH_ENV)
        validator = PinValidator(hash_provider=lambda: spec, data_dir=self._tmp())
        self.assertEqual(validator.verify("1234", "s1").result, "OK")
        self.assertEqual(validator.verify("4321", "s1").result, "WRONG")

    def test_upsert_replaces_existing_line_and_keeps_others(self):
        text = "A=1\nEZPAY_PIN_HASH=\nB=2\n"
        out = set_demo_pin.upsert_env(text, "EZPAY_PIN_HASH=new")
        self.assertEqual(out, "A=1\nEZPAY_PIN_HASH=new\nB=2\n")

    def test_upsert_appends_when_missing(self):
        out = set_demo_pin.upsert_env("A=1\n", "EZPAY_PIN_HASH=new")
        self.assertEqual(out, "A=1\nEZPAY_PIN_HASH=new\n")

    def _tmp(self):
        import tempfile
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name


if __name__ == "__main__":
    unittest.main()
